# File: farsiland_scraper/spiders/movies_spider.py
# Version: 5.0.0
# Last Updated: 2025-04-30 14:00

"""
Spider for scraping movies from Farsiland.

This spider:
1. Extracts movie metadata (title, year, description, cast, etc.)
2. Resolves and extracts video file links for each movie
3. Handles pagination and sitemap-based URL discovery

Changelog:
- [5.0.0] Complete rewrite with simplified architecture
- [5.0.0] Separated extraction logic into focused methods
- [5.0.0] Added comprehensive error handling with fallbacks
- [5.0.0] Integrated with improved VideoLinkResolver
- [5.0.0] Standardized logging with proper context
- [5.0.0] Optimized content detection and filtering
- [4.1.6] Verified compatibility with fixed run.py for proper CLI limit handling
- [4.1.5] Fixed limit handling to respect max_items parameter properly
- [4.1.4] Fixed video file extraction to properly capture MP4 links from redirects
- [4.1.3] Patched unicode arrow logging in _resolve_links to use ASCII fallback
"""

import scrapy
import re
import json
import asyncio
import logging
from typing import Generator, Optional, Dict, List, Any, Set, Tuple
from urllib.parse import urljoin
from bs4 import BeautifulSoup
import aiohttp

from farsiland_scraper.items import MovieItem, VideoFileItem
from farsiland_scraper.config import (
    CONTENT_ZONES,
    LOGGER,
    MAX_ITEMS_PER_CATEGORY,
    USE_SITEMAP,
    PARSED_SITEMAP_PATH,
    BASE_URL
)
from farsiland_scraper.fetch import fetch_sync
from farsiland_scraper.resolvers.video_link_resolver import (
    VideoLinkResolver,
    extract_quality_from_url
)

# Constants for URL validation and content extraction
MOVIE_URL_PATTERN = r"https?://[^/]+/movies/[^/]+/?$"
CONTENT_TYPE = "movies"


class MoviesSpider(scrapy.Spider):
    """
    Spider for extracting movies and their video files.
    
    This spider can operate in two modes:
    1. Sitemap-based: Using pre-parsed sitemap URLs
    2. Crawl-based: Starting from movie index pages
    """
    
    name = "movies"
    allowed_domains = ["farsiland.com"]
    
    def __init__(self, *args, **kwargs):
        """
        Initialize the movies spider.
        
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
        self.sitemap_map = {}  # Maps URLs to lastmod timestamps
        
        # Load from sitemap if no start URLs provided
        if not self.start_urls:
            if USE_SITEMAP:
                self._load_sitemap_urls()
            else:
                # Default to movies index if no sitemap or start URLs
                self.start_urls = [CONTENT_ZONES["movies"]]
        
        # Create resolver for video links
        self.video_resolver = VideoLinkResolver()
        
        LOGGER.info(f"MoviesSpider initialized with max_items={self.max_items}, start_urls={len(self.start_urls)}")
    
    def _load_sitemap_urls(self) -> None:
        """
        Load movie URLs from parsed sitemap file.
        
        This method populates both sitemap_map (dictionary) and start_urls (list).
        """
        try:
            with open(PARSED_SITEMAP_PATH, 'r', encoding='utf-8') as f:
                sitemap = json.load(f)
                
                # Get movie entries from the sitemap
                movie_entries = sitemap.get(CONTENT_TYPE, [])
                if not movie_entries:
                    LOGGER.warning(f"No {CONTENT_TYPE} entries found in sitemap")
                    return
                
                LOGGER.info(f"Found {len(movie_entries)} {CONTENT_TYPE} entries in sitemap")
                
                # Process each entry and store valid URLs
                valid_entries = []
                for entry in movie_entries:
                    if isinstance(entry, dict) and "url" in entry:
                        url = entry["url"].rstrip("/")
                        if self._is_movie_url(url):
                            self.sitemap_map[url] = entry.get("lastmod")
                            valid_entries.append(entry)
                
                # Apply limit to the number of URLs to process
                limited_entries = valid_entries[:self.max_items]
                self.start_urls = [entry["url"] for entry in limited_entries]
                
                LOGGER.info(f"Loaded {len(self.sitemap_map)} movie URLs from sitemap")
                LOGGER.info(f"Using first {len(self.start_urls)} URLs based on max_items={self.max_items}")
                
        except Exception as e:
            LOGGER.error(f"Failed to load sitemap data: {e}", exc_info=True)
    
    def start_requests(self) -> Generator:
        """
        Generate initial requests from start URLs.
        
        Yields:
            Scrapy Requests to movie pages
        """
        LOGGER.info(f"Starting requests for {len(self.start_urls)} movie URLs")
        
        for i, url in enumerate(self.start_urls, 1):
            if self.processed_count >= self.max_items:
                LOGGER.info(f"Reached max_items limit ({self.max_items}), stopping")
                break
                
            LOGGER.debug(f"Scheduling request {i}/{len(self.start_urls)}: {url}")
            yield scrapy.Request(url=url, callback=self.parse)
    
    def parse(self, response) -> Generator:
        """
        Parse a movie page to extract metadata and video links.
        
        Args:
            response: Scrapy response object
            
        Yields:
            MovieItem with extracted data
        """
        url = response.url.rstrip("/")
        LOGGER.info(f"Parsing movie: {url}")
        
        # Check if URL is a valid movie page
        if not self._is_movie_url(url):
            LOGGER.info(f"Skipping non-movie URL: {url}")
            return
        
        # Check if we've reached the item limit
        if self.processed_count >= self.max_items:
            LOGGER.info(f"Reached max_items limit of {self.max_items}, stopping")
            self.crawler.engine.close_spider(self, f"Reached limit of {self.max_items} items")
            return
        
        # Fetch cached or fresh HTML content
        lastmod = self.sitemap_map.get(url)
        html = fetch_sync(url, content_type=CONTENT_TYPE, lastmod=lastmod)
        
        if not html:
            LOGGER.warning(f"Failed to fetch HTML for {url}")
            return
        
        try:
            # Parse the HTML content
            soup = BeautifulSoup(html, 'html.parser')
            
            # Create movie item and extract data
            movie = self._create_movie_item(url, lastmod)
            
            # Extract basic metadata
            self._extract_titles(movie, soup)
            self._extract_metadata(movie, soup)
            self._extract_people(movie, soup)
            self._extract_description(movie, soup)
            self._extract_engagement_data(movie, soup)
            
            # Extract video files
            self._extract_video_files(movie, soup)
            
            # Log the result
            self._log_extraction_result(movie)
            
            # Increment the processed count
            self.processed_count += 1
            LOGGER.info(f"Processed {self.processed_count}/{self.max_items} movies")
            
            # Yield the movie item
            yield movie
            
        except Exception as e:
            LOGGER.error(f"Error parsing movie {url}: {e}", exc_info=True)
    
    def _create_movie_item(self, url: str, lastmod: Optional[str]) -> MovieItem:
        """
        Create a new MovieItem with initial values.
        
        Args:
            url: The movie URL
            lastmod: Last modification timestamp from sitemap
            
        Returns:
            Initialized MovieItem
        """
        return MovieItem(
            url=url,
            sitemap_url=url,
            lastmod=lastmod,
            is_new=1,
            video_files=[]
        )
    
    def _extract_titles(self, movie: MovieItem, soup: BeautifulSoup) -> None:
        """
        Extract the movie titles (English and Farsi) from the HTML.
        
        Args:
            movie: Movie item to update
            soup: BeautifulSoup object with parsed HTML
        """
        try:
            # Extract English title
            title_selectors = [".data h1", "h1.player-title", "h1"]
            for selector in title_selectors:
                title_tag = soup.select_one(selector)
                if title_tag:
                    movie['title_en'] = title_tag.get_text(strip=True)
                    break
            
            # Fallback if no title found
            if not movie.get('title_en'):
                movie['title_en'] = "Unknown Movie"
                LOGGER.warning(f"Could not extract English title for {movie['url']}")
            
            # Extract Farsi title
            farsi_title_selectors = [".data h2", ".data h3", ".custom_fields span.valor.original"]
            for selector in farsi_title_selectors:
                title_tag = soup.select_one(selector)
                if title_tag:
                    movie['title_fa'] = title_tag.get_text(strip=True)
                    break
                    
        except Exception as e:
            LOGGER.warning(f"Error extracting titles: {e}")
            if not movie.get('title_en'):
                movie['title_en'] = "Unknown Movie"
    
    def _extract_metadata(self, movie: MovieItem, soup: BeautifulSoup) -> None:
        """
        Extract metadata including poster, release date, year, and ratings.
        
        Args:
            movie: Movie item to update
            soup: BeautifulSoup object with parsed HTML
        """
        try:
            # Extract poster image
            poster_selectors = [".poster img", "meta[property='og:image']"]
            for selector in poster_selectors:
                poster_tag = soup.select_one(selector)
                if poster_tag:
                    if selector.startswith("meta") and poster_tag.has_attr("content"):
                        movie['poster'] = poster_tag["content"]
                        break
                    elif poster_tag.has_attr("src"):
                        movie['poster'] = poster_tag["src"]
                        break
                    elif poster_tag.has_attr("data-src"):
                        movie['poster'] = poster_tag["data-src"]
                        break
            
            # Extract release date
            date_selectors = [".extra span.date", ".date[itemprop='dateCreated']"]
            for selector in date_selectors:
                date_tag = soup.select_one(selector)
                if date_tag:
                    movie['release_date'] = date_tag.get_text(strip=True)
                    break
            
            # Extract year
            if movie.get('release_date'):
                # Try to extract year from release date
                match = re.search(r"(\d{4})", movie['release_date'])
                if match:
                    movie['year'] = int(match.group(1))
            
            if not movie.get('year'):
                # Try to extract year from URL
                match = re.search(r"/movies-(\d{4})", movie['url'])
                if match:
                    movie['year'] = int(match.group(1))
            
            # Extract ratings
            rating_selectors = [".dt_rating_vgs", "span[itemprop='ratingValue']"]
            for selector in rating_selectors:
                rating_tag = soup.select_one(selector)
                if rating_tag:
                    try:
                        movie['rating'] = float(rating_tag.get_text(strip=True))
                        break
                    except ValueError:
                        pass
            
            rating_count_selectors = [".rating-count", "span[itemprop='ratingCount']"]
            for selector in rating_count_selectors:
                count_tag = soup.select_one(selector)
                if count_tag:
                    try:
                        count_text = count_tag.get_text(strip=True).replace(',', '')
                        movie['rating_count'] = int(count_text)
                        break
                    except ValueError:
                        pass
                        
        except Exception as e:
            LOGGER.warning(f"Error extracting metadata: {e}")
    
    def _extract_people(self, movie: MovieItem, soup: BeautifulSoup) -> None:
        """
        Extract people data including genres, directors, and cast.
        
        Args:
            movie: Movie item to update
            soup: BeautifulSoup object with parsed HTML
        """
        try:
            # Extract genres
            movie['genres'] = [a.text.strip() for a in soup.select(".sgeneros a") if a.text.strip()]
            
            # Extract directors
            movie['directors'] = [
                a.text.strip() for a in soup.select("#cast [itemprop='director'] a") if a.text.strip()
            ]
            
            # Extract cast
            movie['cast'] = [
                a.text.strip() for a in soup.select("#cast [itemprop='actor'] a") if a.text.strip()
            ]
            
        except Exception as e:
            LOGGER.warning(f"Error extracting people data: {e}")
            # Initialize empty lists for any missing attributes
            if 'genres' not in movie:
                movie['genres'] = []
            if 'directors' not in movie:
                movie['directors'] = []
            if 'cast' not in movie:
                movie['cast'] = []
    
    def _extract_description(self, movie: MovieItem, soup: BeautifulSoup) -> None:
        """
        Extract movie description/synopsis.
        
        Args:
            movie: Movie item to update
            soup: BeautifulSoup object with parsed HTML
        """
        try:
            # Try different selectors for description
            description_selectors = [".wp-content p", ".description p"]
            
            for selector in description_selectors:
                desc_tags = soup.select(selector)
                if desc_tags:
                    movie['description'] = " ".join(tag.get_text(strip=True) for tag in desc_tags)
                    break
                    
        except Exception as e:
            LOGGER.warning(f"Error extracting description: {e}")
            movie['description'] = ""
    
    def _extract_engagement_data(self, movie: MovieItem, soup: BeautifulSoup) -> None:
        """
        Extract engagement data like social shares and comments.
        
        Args:
            movie: Movie item to update
            soup: BeautifulSoup object with parsed HTML
        """
        try:
            # Extract social shares count
            social_count = soup.select_one("#social_count")
            if social_count:
                try:
                    movie['social_shares'] = int(social_count.get_text(strip=True).replace(',', ''))
                except ValueError:
                    pass
            
            # Extract comments count
            comments_title = soup.select_one(".comments-title")
            if comments_title:
                match = re.search(r"\((\d+)\)", comments_title.text)
                if match:
                    movie['comments_count'] = int(match.group(1))
                    
        except Exception as e:
            LOGGER.warning(f"Error extracting engagement data: {e}")
    
    def _extract_video_files(self, movie: MovieItem, soup: BeautifulSoup) -> None:
        """
        Extract video file information from the HTML.
        
        Args:
            movie: Movie item to update
            soup: BeautifulSoup object with parsed HTML
        """
        try:
            # Find file entries in download table
            file_entries = []
            
            # Look for fileids in download table rows
            for row in soup.select("#download table tr[id^='link-']"):
                fileid = row.select_one("input[name='fileid']")
                quality = (row.select_one("strong.quality")
                          or row.select_one("td:nth-child(2)"))
                size = row.select_one("td:nth-child(3)")
                
                if fileid and fileid.has_attr("value"):
                    file_entries.append({
                        "fileid": fileid['value'],
                        "quality": quality.text.strip() if quality else "unknown",
                        "size": size.text.strip() if size else ""
                    })
            
            # If no file entries found in table, look for forms
            if not file_entries:
                for form in soup.select("form[id^='dlform']"):
                    fnode = form.select_one("input[name='fileid']")
                    if fnode and fnode.has_attr("value"):
                        file_entries.append({
                            "fileid": fnode['value'],
                            "quality": "unknown",
                            "size": ""
                        })
            
            # If file entries found, resolve the links
            if file_entries:
                LOGGER.debug(f"Found {len(file_entries)} file entries to resolve")
                video_files = asyncio.run(self._resolve_links(file_entries))
                movie['video_files'] = video_files
            
            # If no video files found or resolved, look for direct MP4 links
            if not movie['video_files']:
                for a in soup.select("a[href$='.mp4']"):
                    href = a.get("href")
                    if href:
                        quality = extract_quality_from_url(href)
                        movie['video_files'].append({
                            "quality": quality,
                            "url": href,
                            "mirror_url": None,
                            "size": ""
                        })
                if movie['video_files']:
                    LOGGER.info(f"Found {len(movie['video_files'])} direct MP4 links")
                else:
                    LOGGER.warning(f"No video files found for {movie['url']}")
                    
        except Exception as e:
            LOGGER.error(f"Error extracting video files: {e}", exc_info=True)
    
    async def _resolve_links(self, file_entries: List[Dict[str, str]]) -> List[Dict[str, str]]:
        """
        Resolve download links for the file entries.
        
        Args:
            file_entries: List of file entries with fileids
            
        Returns:
            List of video file dictionaries
        """
        video_files = []
        
        try:
            async with aiohttp.ClientSession() as session:
                # Establish cookies
                await session.get(BASE_URL)
                
                # Process each file entry
                for entry in file_entries:
                    try:
                        fileid = entry.get('fileid')
                        if not fileid:
                            continue
                        
                        LOGGER.debug(f"Resolving fileid: {fileid}")
                        
                        # Use the improved VideoLinkResolver
                        links = await self.video_resolver.get_video_links(session, fileid)
                        
                        if links:
                            for link in links:
                                video_files.append({
                                    "quality": entry.get("quality", link.get("quality", "unknown")),
                                    "url": link["url"],
                                    "mirror_url": link.get("mirror_url"),
                                    "size": entry.get("size", "")
                                })
                        else:
                            LOGGER.warning(f"No links resolved for fileid {fileid}")
                            
                    except Exception as e:
                        LOGGER.warning(f"Failed to resolve fileid={entry.get('fileid')}: {e}")
                        
                return video_files
                
        except Exception as e:
            LOGGER.error(f"Error in link resolution: {e}", exc_info=True)
            return video_files
    
    def _log_extraction_result(self, movie: MovieItem) -> None:
        """
        Log the result of the extraction process.
        
        Args:
            movie: The extracted movie item
        """
        title = movie.get('title_en', 'Unknown')
        year = movie.get('year', 'Unknown')
        video_count = len(movie.get('video_files', []))
        
        LOGGER.info(f"Extracted: {title} ({year}) with {video_count} video files")
    
    def _is_movie_url(self, url: str) -> bool:
        """
        Check if a URL is a valid movie page.
        
        Args:
            url: URL to check
            
        Returns:
            True if the URL is a valid movie page
        """
        if not url:
            return False
            
        # Use regular expression to validate URL format
        return bool(re.match(MOVIE_URL_PATTERN, url))