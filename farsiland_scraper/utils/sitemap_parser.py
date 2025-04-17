# File: farsiland_scraper/utils/sitemap_parser.py
# Version: 4.0.0
# Last Updated: 2025-04-25

"""
Sitemap parser for Farsiland scraper.

Parses sitemap.xml files to extract URLs for scraping. Supports:
- Sitemap index parsing
- RSS feed monitoring for updates
- URL categorization by content type
- Incremental updates
"""

import logging
import os
import requests
import time
import json
import re
import xml.etree.ElementTree as ET
from bs4 import BeautifulSoup
from urllib.parse import urlparse, urljoin
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple, Any

from farsiland_scraper.config import BASE_URL, LOGGER, CACHE_DIR

# Base configuration
SITEMAP_INDEX_URL = f"{BASE_URL}/sitemap_index.xml"
RSS_FEED_URL = f"{BASE_URL}/feed"
DEFAULT_OUTPUT_FILE = os.path.join(CACHE_DIR, "parsed_urls.json")
LAST_CHECK_FILE = os.path.join(CACHE_DIR, "last_check.json")

# Content patterns for URL categorization
CONTENT_PATTERNS = {
    "movies": [
        r"/movies/[^/]+/?$",
        r"/movies-\d{4}/[^/]+/?$",
        r"/old-iranian-movies/[^/]+/?$"
    ],
    "shows": [
        r"/tvshows/[^/]+/?$",
        r"/series-22/[^/]+/?$",
        r"/iranian-series/[^/]+/?$"
    ],
    "episodes": [
        r"/episodes/[^/]+/?$"
    ]
}

class RequestManager:
    """Handles HTTP requests with retries and error handling."""
    
    def __init__(self, max_retries: int = 3, timeout: int = 10, delay: int = 2):
        """
        Initialize the request manager.
        
        Args:
            max_retries: Maximum number of retry attempts
            timeout: Request timeout in seconds
            delay: Base delay between retries (will use exponential backoff)
        """
        self.max_retries = max_retries
        self.timeout = timeout
        self.delay = delay
        
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xml,application/xhtml+xml,application/json;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5'
        })
    
    def get(self, url: str) -> Optional[bytes]:
        """
        Send a GET request with retries and error handling.
        
        Args:
            url: URL to fetch
            
        Returns:
            Response content as bytes, or None if request failed
        """
        for attempt in range(self.max_retries):
            try:
                LOGGER.debug(f"Requesting {url} (attempt {attempt+1}/{self.max_retries})")
                response = self.session.get(url, timeout=self.timeout)
                response.raise_for_status()
                return response.content
            except requests.RequestException as e:
                # More specific error messages based on exception type
                if isinstance(e, requests.ConnectionError):
                    LOGGER.warning(f"Connection error for {url}: {e}")
                elif isinstance(e, requests.Timeout):
                    LOGGER.warning(f"Timeout error for {url}: {e}")
                elif isinstance(e, requests.HTTPError):
                    LOGGER.warning(f"HTTP error {e.response.status_code} for {url}: {e}")
                else:
                    LOGGER.warning(f"Request error for {url}: {e}")
                
                # Don't retry if we get a 4xx status code (client error)
                if isinstance(e, requests.HTTPError) and 400 <= e.response.status_code < 500:
                    LOGGER.error(f"Client error {e.response.status_code} for {url}, not retrying")
                    return None
                
                # If this isn't the last attempt, wait before retrying
                if attempt < self.max_retries - 1:
                    # Exponential backoff with jitter
                    sleep_time = self.delay * (2 ** attempt) * (0.8 + 0.4 * (time.time() % 1))
                    LOGGER.info(f"Retrying in {sleep_time:.2f} seconds...")
                    time.sleep(sleep_time)
                else:
                    LOGGER.error(f"Failed to fetch {url} after {self.max_retries} attempts")
        
        return None


class SitemapParser:
    """Parses sitemap files and categorizes URLs."""
    
    def __init__(
        self, 
        sitemap_url: str = SITEMAP_INDEX_URL,
        output_file: str = DEFAULT_OUTPUT_FILE,
        rss_url: str = RSS_FEED_URL,
        skip_taxonomies: bool = True
    ):
        """
        Initialize the sitemap parser.
        
        Args:
            sitemap_url: URL of the sitemap index
            output_file: Path to save parsed URLs
            rss_url: URL of the RSS feed
            skip_taxonomies: Whether to skip taxonomy pages
        """
        self.sitemap_url = sitemap_url
        self.output_file = output_file
        self.rss_url = rss_url
        self.last_check_file = LAST_CHECK_FILE
        self.skip_taxonomies = skip_taxonomies
        
        # Initialize the request manager
        self.requester = RequestManager()
        
        # Dictionary to store categorized URLs
        self.results = {
            "movies": [],
            "shows": [],
            "episodes": []
        }
        
        # Ensure output directories exist
        os.makedirs(os.path.dirname(self.output_file), exist_ok=True)
        os.makedirs(os.path.dirname(self.last_check_file), exist_ok=True)
        
    def normalize_url(self, url: str) -> str:
        """
        Normalize a URL to ensure consistent format.
        
        Args:
            url: URL to normalize
            
        Returns:
            Normalized URL
        """
        if not url:
            return ""
        
        # Ensure URL has a scheme
        if not url.startswith(('http://', 'https://')):
            url = urljoin(BASE_URL, url)
        
        # Remove trailing slash for consistency
        return url.rstrip('/')
    
    def categorize_url(self, url: str) -> Optional[str]:
        """
        Determine the category of a URL.
        
        Args:
            url: URL to categorize
            
        Returns:
            Category name or None if URL doesn't match any category
        """
        normalized_url = self.normalize_url(url)
        
        # Skip taxonomy pages if configured
        if self.skip_taxonomies and any(p in normalized_url for p in [
            '/genres/', '/dtcast/', '/dtdirector/', '/dtcreator/', 
            '/dtstudio/', '/dtnetworks/', '/dtyear/'
        ]):
            return None
        
        # Check URL against patterns for each category
        for category, patterns in CONTENT_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, normalized_url):
                    return category
        
        # If no pattern matches, try to infer from URL components
        url_path = urlparse(normalized_url).path
        
        if '/movies/' in url_path:
            return 'movies'
        elif '/tvshows/' in url_path:
            return 'shows'
        elif '/episodes/' in url_path:
            return 'episodes'
        
        # If we still can't categorize, return None
        return None
    
    def check_for_updates(self) -> bool:
        """
        Check if the site has been updated since last check.
        
        Returns:
            True if updates are available, False otherwise
        """
        LOGGER.info("Checking RSS feed for updates...")
        
        # Get last check time
        last_check = self._load_last_check_time()
        if not last_check:
            LOGGER.info("No previous check found, update needed")
            return True
        
        # Get current build date from RSS
        last_build_date = self._get_rss_build_date()
        if not last_build_date:
            LOGGER.warning("Could not get last build date from RSS, assuming update needed")
            return True
        
        LOGGER.info(f"Last site update: {last_build_date}")
        LOGGER.info(f"Last check: {last_check}")
        
        # Compare dates
        if last_build_date > last_check:
            LOGGER.info("Site has been updated since last check")
            return True
        else:
            LOGGER.info("No updates since last check")
            return False
    
    def _load_last_check_time(self) -> Optional[datetime]:
        """
        Load the timestamp of the last check.
        
        Returns:
            Datetime of last check or None if not available
        """
        if not os.path.exists(self.last_check_file):
            return None
        
        try:
            with open(self.last_check_file, 'r') as f:
                data = json.load(f)
                return datetime.fromisoformat(data.get('last_check_time'))
        except (json.JSONDecodeError, ValueError, IOError) as e:
            LOGGER.error(f"Error loading last check time: {e}")
            return None
    
    def _save_last_check_time(self) -> None:
        """Save the current time as the last check time."""
        try:
            with open(self.last_check_file, 'w') as f:
                json.dump({
                    'last_check_time': datetime.now().isoformat()
                }, f)
            LOGGER.info(f"Saved check timestamp: {datetime.now().isoformat()}")
        except IOError as e:
            LOGGER.error(f"Error saving last check time: {e}")
    
    def _get_rss_build_date(self) -> Optional[datetime]:
        """
        Get the last build date from the RSS feed.
        
        Returns:
            Datetime of last build or None if not available
        """
        content = self.requester.get(self.rss_url)
        if not content:
            return None
            
        try:
            root = ET.fromstring(content)
            channel = root.find('channel')
            
            if channel is not None:
                date_element = channel.find('lastBuildDate')
                
                if date_element is not None and date_element.text:
                    date_str = date_element.text
                    
                    # Try standard datetime parsing first
                    try:
                        return datetime.strptime(date_str, "%a, %d %b %Y %H:%M:%S %z")
                    except ValueError:
                        # Fall back to email utils if standard parsing fails
                        try:
                            from email.utils import parsedate_to_datetime
                            return parsedate_to_datetime(date_str)
                        except Exception as e:
                            LOGGER.warning(f"Could not parse RSS date '{date_str}': {e}")
            
            LOGGER.warning("No lastBuildDate found in RSS feed")
            return None
        except Exception as e:
            LOGGER.error(f"Error parsing RSS feed: {e}")
            return None
    
    def parse_sitemap_index(self) -> List[Dict[str, str]]:
        """
        Parse the sitemap index to get individual sitemap URLs.
        
        Returns:
            List of dictionaries with sitemap URLs and lastmod dates
        """
        LOGGER.info(f"Parsing sitemap index: {self.sitemap_url}")
        
        content = self.requester.get(self.sitemap_url)
        if not content:
            LOGGER.error(f"Could not fetch sitemap index: {self.sitemap_url}")
            return []
        
        try:
            soup = BeautifulSoup(content, "xml")
            sitemaps = []
            
            for sitemap in soup.find_all("sitemap"):
                loc = sitemap.find("loc")
                lastmod = sitemap.find("lastmod")
                
                if loc:
                    url = loc.text.strip()
                    entry = {
                        "url": url,
                        "lastmod": lastmod.text.strip() if lastmod else None,
                        "type": self._get_sitemap_type(url)
                    }
                    sitemaps.append(entry)
            
            LOGGER.info(f"Found {len(sitemaps)} sitemaps in the index")
            
            # Sort sitemaps by priority
            return self._sort_sitemaps_by_priority(sitemaps)
        except Exception as e:
            LOGGER.error(f"Error parsing sitemap index: {e}")
            return []
    
    def _get_sitemap_type(self, url: str) -> str:
        """
        Extract sitemap type from URL.
        
        Args:
            url: Sitemap URL
            
        Returns:
            Sitemap type string
        """
        filename = os.path.basename(urlparse(url).path)
        
        # Match patterns like 'movies-sitemap.xml', 'post-sitemap1.xml'
        match = re.match(r'([a-zA-Z_-]+)-sitemap\d*\.xml', filename)
        if match:
            sitemap_type = match.group(1)
            
            # Map various sitemap types to our content categories
            type_mapping = {
                'movies': 'movies',
                'tvshows': 'shows',
                'episodes': 'episodes',
                'post': 'general'
            }
            
            return type_mapping.get(sitemap_type, sitemap_type)
        
        return "other"
    
    def _sort_sitemaps_by_priority(self, sitemaps: List[Dict[str, str]]) -> List[Dict[str, str]]:
        """
        Sort sitemaps by content type priority.
        
        Args:
            sitemaps: List of sitemap entries
            
        Returns:
            Sorted list of sitemap entries
        """
        # Define priority order for sitemap types
        priority_order = {
            'movies': 1,
            'shows': 2,
            'episodes': 3,
            'general': 4,
            'other': 5
        }
        
        # Sort by priority and then by lastmod date
        return sorted(sitemaps, key=lambda x: (
            priority_order.get(x['type'], 999),
            -1 if not x.get('lastmod') else 0  # Put entries without lastmod last within their priority group
        ))
    
    def parse_sitemap(self, sitemap_url: str) -> List[Dict[str, Any]]:
        """
        Parse a single sitemap file to extract URLs.
        
        Args:
            sitemap_url: URL of the sitemap to parse
            
        Returns:
            List of URL entries with metadata
        """
        LOGGER.info(f"Parsing sitemap: {sitemap_url}")
        
        content = self.requester.get(sitemap_url)
        if not content:
            LOGGER.error(f"Could not fetch sitemap: {sitemap_url}")
            return []
        
        try:
            soup = BeautifulSoup(content, "xml")
            entries = []
            
            for url_tag in soup.find_all("url"):
                loc = url_tag.find("loc")
                lastmod = url_tag.find("lastmod")
                
                if loc:
                    url = self.normalize_url(loc.text.strip())
                    entry = {
                        "url": url,
                        "lastmod": lastmod.text.strip() if lastmod else None
                    }
                    entries.append(entry)
            
            LOGGER.info(f"Found {len(entries)} URLs in sitemap: {sitemap_url}")
            return entries
        except Exception as e:
            LOGGER.error(f"Error parsing sitemap {sitemap_url}: {e}")
            return []
    
    def process_sitemaps(self) -> None:
        """Process all sitemaps to categorize URLs."""
        # Get list of sitemaps from the index
        sitemaps = self.parse_sitemap_index()
        if not sitemaps:
            LOGGER.error("No sitemaps found, aborting")
            return
        
        # Process each sitemap
        for sitemap in sitemaps:
            sitemap_url = sitemap["url"]
            sitemap_type = sitemap["type"]
            
            # Skip non-content sitemaps if they don't match our categories
            if sitemap_type not in ["movies", "shows", "episodes", "general"]:
                LOGGER.info(f"Skipping non-content sitemap: {sitemap_url} (type: {sitemap_type})")
                continue
            
            # Parse the sitemap
            entries = self.parse_sitemap(sitemap_url)
            
            # Categorize and store each URL
            for entry in entries:
                category = self.categorize_url(entry["url"])
                if category:
                    self.results[category].append(entry)
        
        # Deduplicate results
        self._deduplicate_results()
    
    def _deduplicate_results(self) -> None:
        """Remove duplicate URLs from results."""
        for category in self.results:
            # Create a dictionary using URL as key to eliminate duplicates
            unique_dict = {}
            for entry in self.results[category]:
                url = entry["url"]
                
                # If URL already exists, keep the entry with the more recent lastmod
                if url in unique_dict:
                    existing_lastmod = unique_dict[url].get("lastmod")
                    new_lastmod = entry.get("lastmod")
                    
                    # If new entry has a more recent lastmod, replace the existing one
                    if new_lastmod and (not existing_lastmod or new_lastmod > existing_lastmod):
                        unique_dict[url] = entry
                else:
                    unique_dict[url] = entry
            
            # Update the results with deduplicated entries
            self.results[category] = list(unique_dict.values())
            
            LOGGER.info(f"Deduplicated {category}: {len(self.results[category])} unique URLs")
    
    def save_results(self) -> bool:
        """
        Save categorized URLs to output file.
        
        Returns:
            True if successful, False otherwise
        """
        try:
            with open(self.output_file, "w", encoding="utf-8") as f:
                json.dump(self.results, f, indent=2)
            
            total_urls = sum(len(v) for v in self.results.values())
            LOGGER.info(f"Saved {total_urls} URLs to {self.output_file}")
            return True
        except IOError as e:
            LOGGER.error(f"Error saving results to {self.output_file}: {e}")
            return False
    
    def run(self) -> bool:
        """
        Run the sitemap parser workflow.
        
        Returns:
            True if successful, False otherwise
        """
        try:
            # Check if site has been updated
            if not self.check_for_updates():
                LOGGER.info("No updates detected, skipping sitemap parsing")
                return True
            
            # Process all sitemaps
            self.process_sitemaps()
            
            # Save results
            success = self.save_results()
            
            # If successful, update last check time
            if success:
                self._save_last_check_time()
                
                # Log summary
                total = 0
                for category, entries in self.results.items():
                    count = len(entries)
                    LOGGER.info(f"{category.capitalize()}: {count} URLs")
                    total += count
                LOGGER.info(f"Total URLs: {total}")
                
                return True
            else:
                LOGGER.error("Failed to save results")
                return False
        except Exception as e:
            LOGGER.error(f"Unexpected error in sitemap parser: {e}", exc_info=True)
            return False


def main() -> bool:
    """
    Main entry point for sitemap parser.
    
    Returns:
        True if successful, False otherwise
    """
    LOGGER.info("Starting sitemap parser")
    parser = SitemapParser()
    success = parser.run()
    
    if success:
        LOGGER.info("Sitemap parsing completed successfully")
    else:
        LOGGER.error("Sitemap parsing failed")
    
    return success


if __name__ == "__main__":
    main()