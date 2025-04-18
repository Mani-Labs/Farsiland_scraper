# File: farsiland_scraper/spiders/series_spider.py
# Version: 6.0.1
# Last Updated: 2025-05-01 11:15

"""
Spider for scraping TV show/series metadata from Farsiland.

This spider:
1. Extracts series metadata (title, poster, season count, episode links, etc.)
2. Discovers episode URLs but does not process them (left to episodes_spider.py)
3. Handles pagination and sitemap-based URL discovery
"""

import scrapy
import re
import json
import logging
from typing import Generator, Dict, Any, Optional, List, Set
from urllib.parse import urljoin
from bs4 import BeautifulSoup

from farsiland_scraper.items import ShowItem
from farsiland_scraper.config import (
    CONTENT_ZONES,
    LOGGER,
    MAX_ITEMS_PER_CATEGORY,
    USE_SITEMAP,
    PARSED_SITEMAP_PATH,
    BASE_URL
)
from farsiland_scraper.fetch import fetch_sync

# Constants for URL validation and content extraction
SERIES_URL_PATTERN = r"https?://[^/]+/tvshows/[^/]+/?$"
CONTENT_TYPE = "shows"  # The database table is "shows" even though the spider is named "series"


class SeriesSpider(scrapy.Spider):
    """
    Spider for extracting TV series metadata and related episode URLs.
    
    This spider extracts series information without processing episode pages,
    which is the responsibility of the episodes_spider.
    """
    
    name = "series"
    allowed_domains = ["farsiland.com"]
    
    def __init__(self, *args, **kwargs):
        """
        Initialize the series spider.
        
        Args:
            start_urls: Optional list of URLs to start crawling from
            max_items: Maximum number of items to crawl (default: from config)
            export_json: Whether to export results to JSON
        """
        super().__init__(*args, **kwargs)
        
        # Initialize counters and limits
        self.processed_count = 0
        self.max_items = int(kwargs.get("max_items", MAX_ITEMS_PER_CATEGORY))
        
        # Initialize URL sources
        self.start_urls = kwargs.get("start_urls", [])
        self.sitemap_urls = {}  # Maps URLs to lastmod timestamps
        
        # Load from sitemap if no start URLs provided
        if not self.start_urls and USE_SITEMAP:
            self._load_sitemap_urls()
        elif not self.start_urls:
            # Default to series index if no sitemap or start URLs
            self.start_urls = [CONTENT_ZONES.get("series", f"{BASE_URL}/series-22/")]
        
        LOGGER.info(f"SeriesSpider initialized with max_items={self.max_items}, start_urls={len(self.start_urls)}")
    
    def _load_sitemap_urls(self) -> None:
        """
        Load series URLs from parsed sitemap file.
        
        This method populates both sitemap_urls (dictionary) and start_urls (list).
        """
        try:
            with open(PARSED_SITEMAP_PATH, 'r', encoding='utf-8') as f:
                sitemap = json.load(f)
                
                # Look for series entries in the sitemap (could be under different keys)
                series_entries = (
                    sitemap.get(CONTENT_TYPE, []) or 
                    sitemap.get("series", []) or 
                    sitemap.get("tvshows", []) or 
                    sitemap.get("shows", [])  # Last fallback
                )
                
                if not series_entries:
                    LOGGER.warning(f"No series entries found in sitemap")
                    return
                
                LOGGER.info(f"Found {len(series_entries)} series entries in sitemap")
                
                # Process each entry and store valid URLs
                valid_entries = []
                for entry in series_entries:
                    if isinstance(entry, dict) and "url" in entry:
                        url = entry["url"].rstrip("/")
                        if self._is_series_url(url):
                            self.sitemap_urls[url] = entry.get("lastmod")
                            valid_entries.append(entry)
                
                # Apply limit to the number of URLs to process
                limited_entries = valid_entries[:self.max_items]
                self.start_urls = [entry["url"] for entry in limited_entries]
                
                LOGGER.info(f"Loaded {len(self.sitemap_urls)} series URLs from sitemap")
                LOGGER.info(f"Using first {len(self.start_urls)} URLs based on max_items={self.max_items}")
                
        except Exception as e:
            LOGGER.error(f"Failed to load sitemap data: {e}", exc_info=True)
    
    def start_requests(self) -> Generator:
        """
        Generate initial requests from start URLs.
        
        Yields:
            Scrapy Requests to series pages
        """
        LOGGER.info(f"Starting requests for {len(self.start_urls)} series URLs")
        
        for i, url in enumerate(self.start_urls, 1):
            if self.processed_count >= self.max_items:
                LOGGER.info(f"Reached max_items limit ({self.max_items}), stopping")
                break
                
            LOGGER.debug(f"Scheduling request {i}/{len(self.start_urls)}: {url}")
            yield scrapy.Request(url=url, callback=self.parse)
    
    def parse(self, response) -> Generator:
        """
        Parse a series page to extract metadata.
        
        Args:
            response: Scrapy response object
            
        Yields:
            ShowItem with extracted data
        """
        url = response.url.rstrip("/")
        LOGGER.info(f"Parsing series: {url}")
        
        # Check if URL is a valid series page
        if not self._is_series_url(url):
            LOGGER.info(f"Skipping non-series URL: {url}")
            return
        
        # Check if we've reached the item limit
        if self.processed_count >= self.max_items:
            LOGGER.info(f"Reached max_items limit of {self.max_items}, stopping")
            self.crawler.engine.close_spider(self, f"Reached limit of {self.max_items} items")
            return
        
        # Fetch cached or fresh HTML content
        lastmod = self.sitemap_urls.get(url)
        html = fetch_sync(url, content_type=CONTENT_TYPE, lastmod=lastmod)
        
        if not html:
            LOGGER.warning(f"Failed to fetch HTML for {url}")
            return
        
        try:
            # Parse the HTML content
            soup = BeautifulSoup(html, 'html.parser')
            
            # Create show item and extract data
            show = self._create_show_item(url, lastmod)
            
            # Extract metadata
            self._extract_title(show, soup)
            self._extract_poster(show, soup)
            self._extract_metadata(show, soup)
            self._extract_genres(show, soup)
            self._extract_people(show, soup)
            
            # Extract seasons and episode URLs
            self._extract_seasons_and_episodes(show, soup)
            
            # Log the result
            self._log_extraction_result(show)
            
            # Increment the processed count
            self.processed_count += 1
            LOGGER.info(f"Processed {self.processed_count}/{self.max_items} series")
            
            # Yield the show item
            yield show
            
        except Exception as e:
            LOGGER.error(f"Error parsing series {url}: {e}", exc_info=True)
    
    def _create_show_item(self, url: str, lastmod: Optional[str]) -> ShowItem:
        """
        Create a new ShowItem with initial values.
        
        Args:
            url: The series URL
            lastmod: Last modification timestamp from sitemap
            
        Returns:
            Initialized ShowItem
        """
        return ShowItem(
            url=url,
            sitemap_url=url,
            lastmod=lastmod,
            is_new=True,
            genres=[],
            directors=[],
            cast=[],
            seasons=[],
            episode_urls=[]
        )
    
    def _extract_title(self, show: ShowItem, soup: BeautifulSoup) -> None:
        """
        Extract the series title from the HTML.
        
        Args:
            show: Show item to update
            soup: BeautifulSoup object with parsed HTML
        """
        try:
            # Try different selectors for the title
            title_selectors = [
                "h1", 
                ".entry-title", 
                "meta[property='og:title']",
                ".sheader .shead h1",
                ".data h1"
            ]
            
            for selector in title_selectors:
                title_tag = soup.select_one(selector)
                if title_tag:
                    # For meta tags, use the content attribute
                    if selector.startswith("meta") and title_tag.has_attr("content"):
                        show['title_en'] = title_tag["content"].strip()
                        break
                    # For regular tags, use the text content
                    show['title_en'] = title_tag.text.strip()
                    break
            
            # Fallback if no title found
            if not show.get('title_en'):
                # Extract from URL as last resort
                slug = show['url'].rstrip('/').split('/')[-1]
                show['title_en'] = slug.replace('-', ' ').title()
                LOGGER.warning(f"Could not extract title for {show['url']}, using slug: {show['title_en']}")
                
        except Exception as e:
            LOGGER.warning(f"Error extracting title: {e}")
            # Set a default title based on URL
            slug = show['url'].rstrip('/').split('/')[-1]
            show['title_en'] = slug.replace('-', ' ').title()
    
    def _extract_poster(self, show: ShowItem, soup: BeautifulSoup) -> None:
        """
        Extract the series poster image URL.
        
        Args:
            show: Show item to update
            soup: BeautifulSoup object with parsed HTML
        """
        try:
            # Try different selectors for poster image
            poster_selectors = [
                ".poster img",
                ".thumb img", 
                "meta[property='og:image']",
                ".imagen img"
            ]
            
            for selector in poster_selectors:
                poster = soup.select_one(selector)
                if poster:
                    # Meta tags use content attribute
                    if selector.startswith("meta") and poster.has_attr("content"):
                        show['poster'] = poster["content"]
                        break
                    # Regular img tags - check various image attributes
                    for attr in ['src', 'data-src', 'data-lazy-src']:
                        if poster.has_attr(attr):
                            show['poster'] = poster[attr]
                            break
                    if show.get('poster'):
                        break
            
            # Ensure poster URL is absolute
            if show.get('poster') and not show['poster'].startswith(('http://', 'https://')):
                show['poster'] = urljoin(show['url'], show['poster'])
                
        except Exception as e:
            LOGGER.warning(f"Error extracting poster: {e}")
            show['poster'] = None
    
    def _extract_metadata(self, show: ShowItem, soup: BeautifulSoup) -> None:
        """
        Extract general metadata like description, ratings, dates.
        
        Args:
            show: Show item to update
            soup: BeautifulSoup object with parsed HTML
        """
        try:
            # Extract description
            description_selectors = [
                ".wp-content", 
                "meta[name='description']",
                "meta[property='og:description']",
                ".description",
                ".contenido .wp-content p"
            ]
            
            for selector in description_selectors:
                desc_el = soup.select_one(selector)
                if desc_el:
                    if selector.startswith("meta") and desc_el.has_attr("content"):
                        show['description'] = desc_el["content"].strip()
                        break
                    show['description'] = desc_el.text.strip()
                    break
            
            # Extract first air date
            date_selectors = [
                "span.date",
                ".extra span.date",
                "meta[property='og:release_date']",
                ".extra .date"
            ]
            
            for selector in date_selectors:
                date_el = soup.select_one(selector)
                if date_el:
                    if selector.startswith("meta") and date_el.has_attr("content"):
                        show['first_air_date'] = date_el["content"].strip()
                        break
                    show['first_air_date'] = date_el.text.strip()
                    break
            
            # Extract rating
            try:
                rating_el = soup.select_one(".imdb span")
                if rating_el:
                    rating_text = rating_el.text.strip()
                    # Extract numeric part
                    rating_match = re.search(r'(\d+(\.\d+)?)', rating_text)
                    if rating_match:
                        show['rating'] = float(rating_match.group(1))
                
                # Extract rating count
                vote_el = soup.select_one(".imdb span.votes")
                if vote_el:
                    vote_text = vote_el.text.strip()
                    # Extract numeric part, may contain comma separators
                    votes_match = re.search(r'([\d,]+)', vote_text)
                    if votes_match:
                        show['rating_count'] = int(votes_match.group(1).replace(',', ''))
            except Exception as e:
                LOGGER.debug(f"Error extracting ratings: {e}")
                # Non-critical, can continue
                
        except Exception as e:
            LOGGER.warning(f"Error extracting metadata: {e}")
    
    def _extract_genres(self, show: ShowItem, soup: BeautifulSoup) -> None:
        """
        Extract genre information.
        
        Args:
            show: Show item to update
            soup: BeautifulSoup object with parsed HTML
        """
        try:
            genres = []
            
            # Try different genre selectors
            genre_selectors = [
                ".sgeneros a",
                "span[itemprop='genre']",
                ".genres a",
                ".metadataContent span.genres a"
            ]
            
            for selector in genre_selectors:
                genre_tags = soup.select(selector)
                if genre_tags:
                    for tag in genre_tags:
                        genre_text = tag.text.strip()
                        if genre_text and genre_text not in genres:
                            genres.append(genre_text)
                    break
            
            show['genres'] = genres
                
        except Exception as e:
            LOGGER.warning(f"Error extracting genres: {e}")
            show['genres'] = []
    
    def _extract_people(self, show: ShowItem, soup: BeautifulSoup) -> None:
        """
        Extract director and cast information.
        
        Args:
            show: Show item to update
            soup: BeautifulSoup object with parsed HTML
        """
        try:
            # Extract directors
            directors = []
            director_selectors = [
                ".person[itemprop='director'] .name",
                ".director a",
                "span[itemprop='director']"
            ]
            
            for selector in director_selectors:
                director_tags = soup.select(selector)
                if director_tags:
                    for tag in director_tags:
                        name = tag.text.strip()
                        if name and name not in directors:
                            directors.append(name)
                    break
            
            show['directors'] = directors
            
            # Extract cast members
            cast = []
            cast_selectors = [
                ".person[itemprop='actor'] .name",
                ".cast a",
                "span[itemprop='actor']"
            ]
            
            for selector in cast_selectors:
                cast_tags = soup.select(selector)
                if cast_tags:
                    for tag in cast_tags:
                        name = tag.text.strip()
                        if name and name not in cast:
                            cast.append(name)
                    break
            
            show['cast'] = cast
                
        except Exception as e:
            LOGGER.warning(f"Error extracting people: {e}")
            show['directors'] = []
            show['cast'] = []
    
    def _extract_seasons_and_episodes(self, show: ShowItem, soup: BeautifulSoup) -> None:
        """
        Extract seasons and episode URLs without processing episode pages.
        
        Args:
            show: Show item to update
            soup: BeautifulSoup object with parsed HTML
        """
        try:
            seasons = []
            episode_urls = set()  # To track all unique episode URLs
            
            # Find season containers
            season_containers = soup.select("div.se-c")
            if not season_containers:
                LOGGER.warning(f"No seasons found for {show['url']}")
                
                # Look for alternative season layout
                alt_containers = soup.select(".seasons .se-c")
                if alt_containers:
                    season_containers = alt_containers
                else:
                    # Try another fallback
                    alt_containers = soup.select(".temporadas > div")
                    if alt_containers:
                        season_containers = alt_containers
            
            # Track total episode count
            total_episode_count = 0
            
            # Process each season
            for i, season_div in enumerate(season_containers, 1):
                # Extract season number
                season_header = season_div.select_one(".se-q .se-t")
                
                try:
                    if season_header:
                        # Try to parse season number from text
                        season_text = season_header.text.strip()
                        season_match = re.search(r'(\d+)', season_text)
                        if season_match:
                            season_number = int(season_match.group(1))
                        else:
                            season_number = i
                    else:
                        season_number = i
                except Exception as e:
                    LOGGER.debug(f"Error parsing season number: {e}")
                    season_number = i
                
                # Find episode list for this season
                episode_list = season_div.select("ul.episodios > li")
                if not episode_list:
                    # Try alternative structure
                    episode_list = season_div.select(".se-a ul > li")
                
                # Store episode data without processing episode pages
                season_episodes = []
                
                for ep_li in episode_list:
                    try:
                        # Find the episode link
                        ep_link = ep_li.select_one(".episodiotitle a")
                        if not ep_link or not ep_link.has_attr("href"):
                            # Try alternative selectors
                            ep_link = ep_li.select_one("a")
                            if not ep_link or not ep_link.has_attr("href"):
                                continue
                        
                        # Get the episode URL
                        ep_url = urljoin(BASE_URL, ep_link['href']).rstrip('/')
                        
                        # Extract episode number
                        num_tag = ep_li.select_one(".numerando")
                        if num_tag and "-" in num_tag.text:
                            try:
                                ep_number = int(num_tag.text.split("-")[1].strip())
                            except (ValueError, IndexError):
                                # Try to extract from URL
                                ep_match = re.search(r'ep(\d+)', ep_url.lower())
                                if ep_match:
                                    ep_number = int(ep_match.group(1))
                                else:
                                    ep_number = len(season_episodes) + 1
                        else:
                            # Try to extract from URL
                            ep_match = re.search(r'ep(\d+)', ep_url.lower())
                            if ep_match:
                                ep_number = int(ep_match.group(1))
                            else:
                                ep_number = len(season_episodes) + 1
                        
                        # Extract episode title
                        ep_title = ep_link.text.strip()
                        
                        # Extract air date if available
                        date_tag = ep_li.select_one(".episodiotitle .date")
                        ep_date = date_tag.text.strip() if date_tag else None
                        
                        # Get thumbnail if available
                        thumb = ep_li.select_one(".thumb img")
                        thumbnail = None
                        if thumb:
                            for attr in ['src', 'data-src', 'data-lazy-src']:
                                if thumb.has_attr(attr):
                                    thumbnail = thumb[attr]
                                    if not thumbnail.startswith(('http://', 'https://')):
                                        thumbnail = urljoin(BASE_URL, thumbnail)
                                    break
                        
                        # Store episode data
                        episode_data = {
                            "episode_number": ep_number,
                            "title": ep_title,
                            "date": ep_date,
                            "url": ep_url,
                            "thumbnail": thumbnail
                        }
                        
                        season_episodes.append(episode_data)
                        episode_urls.add(ep_url)
                        total_episode_count += 1
                        
                    except Exception as e:
                        LOGGER.warning(f"Error processing episode in season {season_number}: {e}")
                
                # Skip empty seasons
                if not season_episodes:
                    continue
                    
                # Sort episodes by number
                season_episodes.sort(key=lambda ep: ep.get('episode_number', 0))
                
                # Add season data
                season_data = {
                    "season_number": season_number,
                    "title": f"Season {season_number}",
                    "episode_count": len(season_episodes),
                    "episodes": season_episodes
                }
                
                seasons.append(season_data)
            
            # Sort seasons by number
            seasons.sort(key=lambda s: s.get('season_number', 0))
            
            # If no seasons found from structured layout, create a default season
            if not seasons and episode_urls:
                # Create a default season with all found episodes
                default_season = {
                    "season_number": 1,
                    "title": "Season 1",
                    "episode_count": len(episode_urls),
                    "episodes": [{"url": url} for url in episode_urls]
                }
                seasons.append(default_season)
            
            # Update show with season and episode data
            show['seasons'] = seasons
            show['season_count'] = len(seasons)
            show['episode_count'] = total_episode_count
            
            # Store all unique episode URLs
            show['episode_urls'] = list(episode_urls)
            
            LOGGER.info(f"Extracted {len(seasons)} seasons with {total_episode_count} episodes")
                
        except Exception as e:
            LOGGER.error(f"Error extracting seasons and episodes: {e}", exc_info=True)
            # Ensure we at least have empty lists to avoid further errors
            show['seasons'] = []
            show['season_count'] = 0
            show['episode_count'] = 0
            show['episode_urls'] = []
    
    def _log_extraction_result(self, show: ShowItem) -> None:
        """
        Log the result of the extraction process.
        
        Args:
            show: The extracted show item
        """
        title = show.get('title_en', 'Unknown')
        seasons = show.get('season_count', 0)
        episodes = show.get('episode_count', 0)
        
        LOGGER.info(f"Extracted series: {title} ({seasons} seasons, {episodes} episodes)")
    
    def _is_series_url(self, url: str) -> bool:
        """
        Check if a URL is a valid series page.
        
        Args:
            url: URL to check
            
        Returns:
            True if the URL is a valid series page
        """
        if not url:
            return False
            
        # Use regular expression to validate URL format
        return bool(re.match(SERIES_URL_PATTERN, url))