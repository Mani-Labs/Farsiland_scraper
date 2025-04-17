# File: farsiland_scraper/spiders/episodes_spider.py
# Version: 6.0.0
# Last Updated: 2025-04-28 15:30

"""
Spider for scraping TV show episodes from Farsiland.

This spider:
1. Extracts episode metadata (title, season/episode numbers, air date, etc.)
2. Resolves and extracts video file links for each episode
3. Handles pagination and sitemap-based URL discovery

Changelog:
- [6.0.0] Complete rewrite with simplified architecture
- [6.0.0] Separated extraction logic into focused methods
- [6.0.0] Added comprehensive error handling with fallbacks
- [6.0.0] Integrated with improved VideoLinkResolver
- [6.0.0] Standardized logging with proper context
- [6.0.0] Optimized content detection and filtering
- [5.0.3] Added proper limit handling to respect max_items parameter
- [5.0.3] Fixed compatibility with the updated run.py
"""

import scrapy
import re
import json
import asyncio
import logging
from typing import Generator, Optional, Dict, List, Any, Set, Tuple
from urllib.parse import urljoin
from bs4 import BeautifulSoup

from farsiland_scraper.items import EpisodeItem, VideoFileItem
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
EPISODE_URL_PATTERN = r"https?://[^/]+/episodes/[^/]+/?$"
CONTENT_TYPE = "episodes"


class EpisodesSpider(scrapy.Spider):
    """
    Spider for extracting TV show episodes and their video files.
    
    This spider can operate in two modes:
    1. Sitemap-based: Using pre-parsed sitemap URLs
    2. Crawl-based: Starting from episode index pages
    """
    
    name = "episodes"
    allowed_domains = ["farsiland.com"]
    
    def __init__(self, *args, **kwargs):
        """
        Initialize the episodes spider.
        
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
            # Default to episodes index if no sitemap or start URLs
            self.start_urls = [CONTENT_ZONES["episodes"]]
        
        # Create resolver for video links
        self.video_resolver = VideoLinkResolver()
        
        LOGGER.info(f"EpisodesSpider initialized with max_items={self.max_items}, start_urls={len(self.start_urls)}")
    
    def _load_sitemap_urls(self) -> None:
        """
        Load episode URLs from parsed sitemap file.
        
        This method populates both sitemap_urls (dictionary) and start_urls (list).
        """
        try:
            with open(PARSED_SITEMAP_PATH, 'r', encoding='utf-8') as f:
                sitemap = json.load(f)
                
                # Get episode entries from the sitemap
                episode_entries = sitemap.get(CONTENT_TYPE, [])
                if not episode_entries:
                    LOGGER.warning(f"No {CONTENT_TYPE} entries found in sitemap")
                    return
                
                LOGGER.info(f"Found {len(episode_entries)} {CONTENT_TYPE} entries in sitemap")
                
                # Process each entry and store valid URLs
                valid_entries = []
                for entry in episode_entries:
                    if isinstance(entry, dict) and "url" in entry:
                        url = entry["url"].rstrip("/")
                        if self._is_episode_url(url):
                            self.sitemap_urls[url] = entry.get("lastmod")
                            valid_entries.append(entry)
                
                # Apply limit to the number of URLs to process
                limited_entries = valid_entries[:self.max_items]
                self.start_urls = [entry["url"] for entry in limited_entries]
                
                LOGGER.info(f"Loaded {len(self.sitemap_urls)} episode URLs from sitemap")
                LOGGER.info(f"Using first {len(self.start_urls)} URLs based on max_items={self.max_items}")
                
        except Exception as e:
            LOGGER.error(f"Failed to load sitemap data: {e}", exc_info=True)
    
    def start_requests(self) -> Generator:
        """
        Generate initial requests from start URLs.
        
        Yields:
            Scrapy Requests to episode pages
        """
        LOGGER.info(f"Starting requests for {len(self.start_urls)} episode URLs")
        
        for i, url in enumerate(self.start_urls, 1):
            if self.processed_count >= self.max_items:
                LOGGER.info(f"Reached max_items limit ({self.max_items}), stopping")
                break
                
            LOGGER.debug(f"Scheduling request {i}/{len(self.start_urls)}: {url}")
            yield scrapy.Request(url=url, callback=self.parse)
    
    def parse(self, response) -> Generator:
        """
        Parse an episode page to extract metadata and video links.
        
        Args:
            response: Scrapy response object
            
        Yields:
            EpisodeItem with extracted data
        """
        url = response.url.rstrip("/")
        LOGGER.info(f"Parsing episode: {url}")
        
        # Check if URL is a valid episode page
        if not self._is_episode_url(url):
            LOGGER.info(f"Skipping non-episode URL: {url}")
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
            
            # Create episode item and extract data
            episode = self._create_episode_item(url, lastmod)
            
            # Extract basic metadata
            self._extract_title(episode, soup)
            self._extract_episode_info(episode, soup, url)
            self._extract_show_info(episode, soup)
            self._extract_media_info(episode, soup)
            
            # Extract video files
            self._extract_video_files(episode, soup)
            
            # Log the result
            self._log_extraction_result(episode)
            
            # Increment the processed count
            self.processed_count += 1
            LOGGER.info(f"Processed {self.processed_count}/{self.max_items} episodes")
            
            # Yield the episode item
            yield episode
            
        except Exception as e:
            LOGGER.error(f"Error parsing episode {url}: {e}", exc_info=True)
    
    def _create_episode_item(self, url: str, lastmod: Optional[str]) -> EpisodeItem:
        """
        Create a new EpisodeItem with initial values.
        
        Args:
            url: The episode URL
            lastmod: Last modification timestamp from sitemap
            
        Returns:
            Initialized EpisodeItem
        """
        return EpisodeItem(
            url=url,
            sitemap_url=url,
            lastmod=lastmod,
            is_new=True,
            video_files=[]
        )
    
    def _extract_title(self, episode: EpisodeItem, soup: BeautifulSoup) -> None:
        """
        Extract the episode title from the HTML.
        
        Args:
            episode: Episode item to update
            soup: BeautifulSoup object with parsed HTML
        """
        try:
            # Try different selectors for the title
            title_selectors = [
                ".player-title", 
                "h1", 
                ".episodiotitle h3", 
                "meta[property='og:title']"
            ]
            
            for selector in title_selectors:
                title_tag = soup.select_one(selector)
                if title_tag:
                    # For meta tags, use the content attribute
                    if selector.startswith("meta") and title_tag.has_attr("content"):
                        episode['title'] = title_tag["content"].strip()
                        break
                    # For regular tags, use the text content
                    episode['title'] = title_tag.text.strip()
                    break
            
            # Fallback if no title found
            if not episode.get('title'):
                episode['title'] = "Unknown Episode"
                LOGGER.warning(f"Could not extract title for {episode['url']}")
                
        except Exception as e:
            LOGGER.warning(f"Error extracting title: {e}")
            episode['title'] = "Unknown Episode"
    
    def _extract_episode_info(self, episode: EpisodeItem, soup: BeautifulSoup, url: str) -> None:
        """
        Extract season and episode numbers from the HTML.
        
        Args:
            episode: Episode item to update
            soup: BeautifulSoup object with parsed HTML
            url: The episode URL for fallback extraction
        """
        try:
            # Default values
            season_number = 1
            episode_number = 1
            
            # Try to extract from the 'numerando' element (format: "1 - 2")
            numerando = soup.select_one(".numerando")
            if numerando:
                parts = numerando.text.strip().split("-")
                if len(parts) == 2:
                    try:
                        season_number = int(parts[0].strip())
                        episode_number = int(parts[1].strip())
                    except ValueError:
                        LOGGER.debug(f"Could not parse numerando: {numerando.text}")
            
            # Fallback: Try to extract from breadcrumbs
            if season_number == 1:
                breadcrumb = soup.select_one(".breadcrumb")
                if breadcrumb:
                    season_text = None
                    for li in breadcrumb.select("li"):
                        text = li.text.strip()
                        if "season" in text.lower():
                            match = re.search(r'season\s*(\d+)', text.lower())
                            if match:
                                try:
                                    season_number = int(match.group(1))
                                except ValueError:
                                    pass
            
            # Fallback: Try to extract from URL
            if episode_number == 1:
                match = re.search(r'ep(?:isode)?[_-]?(\d+)', url.lower())
                if match:
                    try:
                        episode_number = int(match.group(1))
                    except ValueError:
                        pass
            
            # Fallback: Try to extract from title
            if episode_number == 1 and episode.get('title'):
                match = re.search(r'episode\s*(\d+)', episode['title'].lower())
                if match:
                    try:
                        episode_number = int(match.group(1))
                    except ValueError:
                        pass
            
            episode['season_number'] = season_number
            episode['episode_number'] = episode_number
            
        except Exception as e:
            LOGGER.warning(f"Error extracting episode info: {e}")
            episode['season_number'] = 1
            episode['episode_number'] = 1
    
    def _extract_show_info(self, episode: EpisodeItem, soup: BeautifulSoup) -> None:
        """
        Extract the parent show URL and related information.
        
        Args:
            episode: Episode item to update
            soup: BeautifulSoup object with parsed HTML
        """
        try:
            # Try different selectors for show link
            show_link_selectors = [
                ".breadcrumb li:nth-last-child(2) a",
                "div.pag_episodes a[href*='/tvshows/']",
                "a[href*='/tvshows/']",
                "a[href*='/series/']"
            ]
            
            for selector in show_link_selectors:
                show_link = soup.select_one(selector)
                if show_link and show_link.has_attr("href"):
                    show_url = show_link['href'].rstrip("/")
                    if '/tvshows/' in show_url or '/series/' in show_url:
                        episode['show_url'] = show_url
                        break
            
            # Fallback if no show URL found
            if not episode.get('show_url'):
                LOGGER.warning(f"Could not extract show URL for {episode['url']}")
                # Create a fallback URL based on episode URL
                base_url = episode['url'].split('/episodes/')[0]
                episode_slug = episode['url'].split('/episodes/')[1]
                show_slug = episode_slug.split('-')[0] if '-' in episode_slug else episode_slug
                episode['show_url'] = f"{base_url}/tvshows/{show_slug}"
                
        except Exception as e:
            LOGGER.warning(f"Error extracting show info: {e}")
            episode['show_url'] = None
    
    def _extract_media_info(self, episode: EpisodeItem, soup: BeautifulSoup) -> None:
        """
        Extract media information (thumbnail, air date).
        
        Args:
            episode: Episode item to update
            soup: BeautifulSoup object with parsed HTML
        """
        try:
            # Extract thumbnail
            thumbnail_selectors = [
                "meta[property='og:image']",
                ".poster img",
                ".thumb img"
            ]
            
            for selector in thumbnail_selectors:
                thumb = soup.select_one(selector)
                if thumb:
                    if selector.startswith("meta") and thumb.has_attr("content"):
                        episode['thumbnail'] = thumb["content"]
                        break
                    elif thumb.has_attr("src"):
                        episode['thumbnail'] = thumb["src"]
                        break
                    elif thumb.has_attr("data-src"):
                        episode['thumbnail'] = thumb["data-src"]
                        break
            
            # Extract air date
            date_selectors = [
                ".extra span.date + span.date",
                ".episodiotitle .date",
                ".date[itemprop='dateCreated']",
                "span.date"
            ]
            
            for selector in date_selectors:
                date_tag = soup.select_one(selector)
                if date_tag:
                    episode['air_date'] = date_tag.text.strip()
                    break
            
        except Exception as e:
            LOGGER.warning(f"Error extracting media info: {e}")
    
    def _extract_video_files(self, episode: EpisodeItem, soup: BeautifulSoup) -> None:
        """
        Extract video file information from the HTML.
        
        Args:
            episode: Episode item to update
            soup: BeautifulSoup object with parsed HTML
        """
        try:
            # Find file entries in download table
            file_entries = []
            
            # Look for fileids in download table rows
            for row in soup.select("#download table tr[id^='link-']"):
                fileid = row.select_one("form input[name='fileid']")
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
            
            # If no fileids found, look for direct MP4 links
            if not file_entries:
                for a in soup.select("a[href$='.mp4']"):
                    href = a.get("href")
                    if href:
                        quality = extract_quality_from_url(href)
                        episode['video_files'].append({
                            "quality": quality,
                            "url": href,
                            "mirror_url": None,
                            "size": ""
                        })
                if episode['video_files']:
                    LOGGER.info(f"Found {len(episode['video_files'])} direct MP4 links")
                    return
            
            # If file entries found, resolve the links
            if file_entries:
                LOGGER.debug(f"Found {len(file_entries)} file entries to resolve")
                video_files = asyncio.run(self._resolve_links(file_entries))
                episode['video_files'] = video_files
            else:
                LOGGER.warning(f"No video files found for {episode['url']}")
                
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
        import aiohttp
        
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
    
    def _log_extraction_result(self, episode: EpisodeItem) -> None:
        """
        Log the result of the extraction process.
        
        Args:
            episode: The extracted episode item
        """
        title = episode.get('title', 'Unknown')
        season = episode.get('season_number', 0)
        ep_num = episode.get('episode_number', 0)
        video_count = len(episode.get('video_files', []))
        
        LOGGER.info(f"Extracted: S{season}E{ep_num} - {title} ({video_count} video files)")
    
    def _is_episode_url(self, url: str) -> bool:
        """
        Check if a URL is a valid episode page.
        
        Args:
            url: URL to check
            
        Returns:
            True if the URL is a valid episode page
        """
        if not url:
            return False
            
        # Use regular expression to validate URL format
        return bool(re.match(EPISODE_URL_PATTERN, url))