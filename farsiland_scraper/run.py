# File: farsiland_scraper/run.py
# Version: 3.1.0
# Last Updated: 2025-04-21

# Changelog:
# - Improved URL detection logic for more accurate content type determination
# - Fixed default max_items value to be more reasonable
# - Simplified complex nested conditionals
# - Added better error handling for common failures
# - Improved code organization and readability

import os
import sys
import time
import json
import argparse
import datetime
import logging
import signal
import re
import importlib
from typing import Dict, List, Any, Optional, Set, Tuple
from pathlib import Path

# Add project root to path for imports
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Import Scrapy components
from scrapy.crawler import CrawlerProcess
from scrapy.settings import Settings
from scrapy.utils.project import get_project_settings

# Import project components
from farsiland_scraper.config import (
    LOGGER, 
    SCRAPE_INTERVAL, 
    PARSED_SITEMAP_PATH,
    MAX_ITEMS_PER_CATEGORY
)
from farsiland_scraper.database.models import Database
from farsiland_scraper.utils.new_item_tracker import NewItemTracker
from farsiland_scraper.utils.sitemap_parser import SitemapParser
from farsiland_scraper.spiders.series_spider import SeriesSpider
from farsiland_scraper.spiders.episodes_spider import EpisodesSpider
from farsiland_scraper.spiders.movies_spider import MoviesSpider

# Define constants
DEFAULT_SPIDER_MODULES = ["farsiland_scraper.spiders"]
SPIDER_TYPES = {
    'series': SeriesSpider,
    'episodes': EpisodesSpider,
    'movies': MoviesSpider,
    'all': None  # Special value meaning "all spiders"
}

# URL patterns for content type detection
CONTENT_PATTERNS = {
    'movies': r"https?://[^/]+/movies/[^/]+/?$",
    'episodes': r"https?://[^/]+/episodes/[^/]+/?$", 
    'series': r"https?://[^/]+/tvshows/[^/]+/?$"
}

class ScrapeManager:
    """
    Manager class for controlling the scraping process.
    Handles initialization, command processing, and orchestration.
    """

    def __init__(self, args: argparse.Namespace):
        """Initialize the scrape manager with parsed arguments."""
        self.args = args
        self.process = None
        self.start_time = None
        self.interrupted = False

        # Configure signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self.handle_interrupt)
        signal.signal(signal.SIGTERM, self.handle_interrupt)

        # Setup logging
        self.setup_logging()

        # Initialize crawler settings
        self.settings = self.load_scrapy_settings()

        # Initialize sitemap data
        self.sitemap_data = {}
        
        try:
            # Handle specific URL if provided
            if args.url:
                self.sitemap_data = self._create_sitemap_from_url(args.url)
                # Force sitemap mode when using specific URL
                self.args.sitemap = True
            else:
                # Load sitemap data if specified
                if args.sitemap:
                    self.sitemap_data = self.load_sitemap_data()
        except Exception as e:
            LOGGER.error(f"Error initializing sitemap data: {e}", exc_info=True)
            self.sitemap_data = {}

    def _create_sitemap_from_url(self, url: str) -> Dict[str, List[Dict[str, str]]]:
        """
        Create a sitemap dictionary from a specific URL.
        Determines the content type based on URL pattern.
        
        Args:
            url: The URL to create a sitemap entry for
            
        Returns:
            A dictionary with content type keys and URL entry lists
        """
        # Initialize empty sitemap
        sitemap_data = {
            "movies": [],
            "episodes": [],
            "series": []
        }
        
        # Clean the URL (remove trailing slash if present)
        url = url.rstrip("/")
        
        # Determine content type based on URL pattern
        content_type = self.detect_content_type(url)
        
        if content_type:
            # Add the URL to the appropriate content type
            sitemap_data[content_type].append({"url": url})
            LOGGER.info(f"Created sitemap with 1 {content_type} URL: {url}")
        else:
            LOGGER.warning(f"Could not determine content type for URL: {url}, skipping")
            
        return sitemap_data
    
    def detect_content_type(self, url: str) -> Optional[str]:
        """
        Detect content type based on URL pattern.
        
        Args:
            url: The URL to analyze
            
        Returns:
            Content type string or None if can't be determined
        """
        if not url:
            return None
            
        # Check against patterns
        for content_type, pattern in CONTENT_PATTERNS.items():
            if re.match(pattern, url):
                return content_type
                
        # If no direct match, try to infer from URL segments
        url_parts = url.lower()
        if "/movies/" in url_parts:
            return "movies"
        elif "/episodes/" in url_parts:
            return "episodes"
        elif "/tvshows/" in url_parts or "/series" in url_parts:
            return "series"
            
        # Default to None if can't determine
        return None
    
    def setup_logging(self):
        """Configure logging for the scrape manager."""
        log_level = logging.DEBUG if self.args.verbose else logging.INFO
        LOGGER.setLevel(log_level)

        # Log to file if specified
        if self.args.log_file:
            try:
                log_dir = os.path.dirname(self.args.log_file)
                if log_dir and not os.path.exists(log_dir):
                    os.makedirs(log_dir, exist_ok=True)

                file_handler = logging.FileHandler(self.args.log_file)
                file_formatter = logging.Formatter(
                    '%(asctime)s [%(levelname)s] %(name)s: %(message)s'
                )
                file_handler.setFormatter(file_formatter)
                LOGGER.addHandler(file_handler)
            except Exception as e:
                LOGGER.error(f"Failed to setup file logging: {e}")

    def load_scrapy_settings(self) -> Settings:
        """
        Load Scrapy settings from the project.
        
        Returns:
            Settings: Scrapy settings object
        """
        try:
            settings = Settings()
            project_settings = get_project_settings()

            for key, value in project_settings.items():
                settings.set(key, value)

            # Apply custom settings from arguments
            settings.set('LOG_LEVEL', 'DEBUG' if self.args.verbose else 'INFO')

            if self.args.concurrent_requests:
                settings.set('CONCURRENT_REQUESTS', self.args.concurrent_requests)

            if self.args.download_delay:
                settings.set('DOWNLOAD_DELAY', self.args.download_delay)
                
            # Handle force refresh
            if self.args.force_refresh:
                settings.set('HTTPCACHE_ENABLED', False)

            return settings
        except Exception as e:
            LOGGER.error(f"Error loading Scrapy settings: {e}")
            # Return default settings as fallback
            return Settings()

    def is_valid_content_url(self, url: str, spider_type: str) -> bool:
        """
        Check if a URL is a valid content page for a specific spider type.
        
        Args:
            url: URL to check
            spider_type: Type of spider ('series', 'episodes', 'movies')
        
        Returns:
            bool: True if the URL is a valid content page
        """
        if not url:
            return False
            
        # Use content patterns dictionary for consistency
        pattern = CONTENT_PATTERNS.get(spider_type)
        if not pattern:
            return False
            
        return re.match(pattern, url) is not None

    def load_sitemap_data(self) -> Dict[str, List[Dict[str, str]]]:
        """
        Load parsed sitemap data from JSON file.
        
        Returns:
            Dict containing URLs for different content types
        """
        sitemap_path = self.args.sitemap_file or PARSED_SITEMAP_PATH

        if not os.path.exists(sitemap_path):
            LOGGER.error(f"Sitemap file not found: {sitemap_path}")
            if self.args.update_sitemap:
                try:
                    LOGGER.info("Updating sitemap data...")
                    parser = SitemapParser(output_file=sitemap_path)
                    if parser.run():
                        LOGGER.info(f"Sitemap updated successfully: {sitemap_path}")
                    else:
                        LOGGER.error("Failed to update sitemap")
                        return {}
                except Exception as e:
                    LOGGER.error(f"Error updating sitemap: {e}")
                    return {}
            else:
                LOGGER.error("Use --update-sitemap to generate the sitemap file")
                return {}

        try:
            with open(sitemap_path, 'r', encoding='utf-8') as f:
                sitemap_data = json.load(f)

            # Convert format if needed (older format compatibility)
            if 'shows' in sitemap_data and isinstance(sitemap_data['shows'], list):
                # Rename 'shows' to 'series' for consistency with spider names
                sitemap_data['series'] = sitemap_data.pop('shows')

            # Print stats
            for category, urls in sitemap_data.items():
                LOGGER.info(f"Loaded {len(urls)} URLs for {category} from sitemap")

            return sitemap_data
        except json.JSONDecodeError as e:
            LOGGER.error(f"Invalid JSON in sitemap file: {e}")
            return {}
        except Exception as e:
            LOGGER.error(f"Error loading sitemap data: {e}")
            return {}

    def get_start_urls(self, spider_type: str) -> List[str]:
        """
        Get start URLs for a specific spider type.
        
        Args:
            spider_type: Type of spider ('series', 'episodes', 'movies')
            
        Returns:
            List of start URLs
        """
        if not self.args.sitemap:
            # Without sitemap, spiders use their default start URLs
            LOGGER.info(f"No sitemap specified, returning empty start_urls for {spider_type}")
            return []

        # Map spider type to sitemap category
        category = 'series' if spider_type == 'series' else spider_type

        # Get URLs from sitemap data
        urls = self.sitemap_data.get(category, [])
        LOGGER.info(f"Found {len(urls)} URLs for {category} in sitemap")

        # Extract URL strings
        start_urls = []
        if urls:
            if isinstance(urls[0], dict) and 'url' in urls[0]:
                start_urls = [entry['url'] for entry in urls]
            else:
                start_urls = urls
            
        # Filter URLs to include only valid content pages
        original_count = len(start_urls)
        valid_urls = [url for url in start_urls if self.is_valid_content_url(url, spider_type)]
        filtered_count = len(valid_urls)
        
        if filtered_count < original_count:
            LOGGER.info(f"Filtered {original_count - filtered_count} category/archive pages from {category} URLs")
        
        # Apply limit if specified
        max_items = self.get_max_items()
        if max_items > 0:
            valid_urls = valid_urls[:max_items]
            LOGGER.info(f"Limiting {category} URLs to {len(valid_urls)} (limit={max_items})")

        LOGGER.info(f"Returning {len(valid_urls)} start_urls for {spider_type}")
        return valid_urls
        
    def get_max_items(self) -> int:
        """
        Get the maximum number of items to process.
        
        Returns:
            int: Maximum number of items to process
        """
        if self.args.limit and self.args.limit > 0:
            return self.args.limit
        return MAX_ITEMS_PER_CATEGORY  # Default from config

    def create_crawler_process(self) -> CrawlerProcess:
        """
        Create a Scrapy crawler process.
        
        Returns:
            CrawlerProcess: Configured crawler process
        """
        try:
            return CrawlerProcess(self.settings)
        except Exception as e:
            LOGGER.error(f"Error creating crawler process: {e}")
            raise

    def run_spiders(self) -> bool:
        """
        Run the specified spiders.
        
        Returns:
            bool: True if successful, False otherwise
        """
        self.start_time = time.time()
        LOGGER.info(f"Starting crawl at {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

        try:
            # Create crawler process
            self.process = self.create_crawler_process()

            # Determine which spiders to run
            spider_types = self.determine_spider_types()
            if not spider_types:
                LOGGER.error("No valid spider types to run")
                return False

            # Configure and add spiders to the process
            for spider_type in spider_types:
                try:
                    self.add_spider_to_process(spider_type)
                except Exception as e:
                    LOGGER.error(f"Error adding spider {spider_type}: {e}")
                    continue

            # Start the crawling process
            LOGGER.info(f"Starting crawl with spiders: {', '.join(spider_types)}")
            self.process.start()

            if not self.interrupted:
                LOGGER.info("Crawling finished successfully")
                return True
            else:
                LOGGER.warning("Crawling was interrupted")
                return False

        except Exception as e:
            LOGGER.error(f"Error running spiders: {e}", exc_info=True)
            return False
        finally:
            elapsed_time = time.time() - self.start_time
            LOGGER.info(f"Total crawl time: {elapsed_time:.2f} seconds")
            
    def determine_spider_types(self) -> List[str]:
        """
        Determine which spider types to run.
        
        Returns:
            List of spider type names
        """
        if self.args.url:
            # When using --url, run only the spider for the appropriate content type
            # Find which content type has URLs in the sitemap
            spider_types = []
            for spider_type, urls in self.sitemap_data.items():
                if urls:
                    spider_types.append(spider_type)
            return spider_types
        else:
            # Otherwise use the specified spiders
            if 'all' in self.args.spiders:
                return ['series', 'episodes', 'movies']
            return [t for t in self.args.spiders if t in SPIDER_TYPES]
            
    def add_spider_to_process(self, spider_type: str) -> None:
        """
        Add a spider to the crawler process.
        
        Args:
            spider_type: Type of spider to add
        """
        spider_class = SPIDER_TYPES.get(spider_type)
        if not spider_class:
            LOGGER.warning(f"Spider class not found for type: {spider_type}")
            return

        # Get start URLs for this spider
        start_urls = self.get_start_urls(spider_type)

        # Get max items
        max_items = self.get_max_items()

        # Spider-specific settings
        spider_settings = {
            'start_urls': start_urls,
            'max_items': max_items,
            'export_json': self.args.export
        }

        # Add the spider to the process
        self.process.crawl(spider_class, **spider_settings)
        LOGGER.info(f"Added {spider_type} spider to crawl queue with {len(start_urls)} URLs and max_items={max_items}")

    def process_new_content(self) -> bool:
        """
        Process newly discovered content.
        
        Returns:
            bool: True if successful, False otherwise
        """
        if not self.args.notify and not self.args.export:
            return True

        try:
            with Database() as db:
                # Export to JSON if requested
                if self.args.export:
                    LOGGER.info("Exporting database to JSON...")
                    success = db.export_to_json(output_path=self.args.export_file)
                    if success:
                        LOGGER.info("Database exported successfully")
                    else:
                        LOGGER.error("Failed to export database")

                # Process and notify about new content if requested
                if self.args.notify:
                    LOGGER.info("Processing new content for notifications...")
                    tracker = NewItemTracker(db)
                    new_content = tracker.get_new_content()

                    if any(new_content.values()):
                        LOGGER.info(
                            f"Found new content: {', '.join(f'{k}: {len(v)}' for k, v in new_content.items() if v)}"
                        )
                        tracker.notify_new_content(new_content)
                    else:
                        LOGGER.info("No new content found")

                    tracker.mark_as_processed(new_content)

            return True
        except Exception as e:
            LOGGER.error(f"Error processing new content: {e}", exc_info=True)
            return False

    def run_once(self) -> bool:
        """
        Run the scraper once.
        
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            if self.args.update_sitemap:
                LOGGER.info("Updating sitemap data...")
                parser = SitemapParser(output_file=self.args.sitemap_file or PARSED_SITEMAP_PATH)
                if not parser.run():
                    LOGGER.error("Failed to update sitemap")
                    return False

                # Reload sitemap data
                self.sitemap_data = self.load_sitemap_data()

            # Run spiders
            success = self.run_spiders()

            # Process new content if scraping was successful
            if success:
                success = self.process_new_content()

            return success
        except Exception as e:
            LOGGER.error(f"Error in run_once: {e}", exc_info=True)
            return False

    def run_daemon(self) -> bool:
        """
        Run the scraper in daemon mode (continuous loop).
        
        Returns:
            bool: True if exited gracefully, False otherwise
        """
        LOGGER.info(f"Starting daemon mode with interval: {SCRAPE_INTERVAL} seconds")

        try:
            while not self.interrupted:
                start_time = time.time()
                LOGGER.info(f"Starting crawl at {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

                try:
                    success = self.run_once()
                    LOGGER.info(f"Crawl {'succeeded' if success else 'failed'}")
                except Exception as e:
                    LOGGER.error(f"Error in daemon crawl cycle: {e}", exc_info=True)
                    success = False
                
                elapsed_time = time.time() - start_time
                sleep_time = max(0, SCRAPE_INTERVAL - elapsed_time)

                if self.interrupted:
                    LOGGER.info("Received interrupt signal, exiting daemon mode")
                    break

                if sleep_time > 0:
                    LOGGER.info(f"Sleeping for {sleep_time:.2f}s until next crawl")

                    # Break sleep into chunks to allow for quicker interruption
                    chunks = 10
                    chunk_time = sleep_time / chunks

                    for _ in range(chunks):
                        if self.interrupted:
                            break
                        time.sleep(chunk_time)

            return True
        except KeyboardInterrupt:
            LOGGER.info("Received keyboard interrupt. Exiting daemon mode...")
            return True
        except Exception as e:
            LOGGER.error(f"Error in daemon mode: {e}", exc_info=True)
            return False

    def handle_interrupt(self, signum, frame):
        """Handle interrupt signals (SIGINT, SIGTERM)."""
        LOGGER.info(f"Received signal {signum}, initiating graceful shutdown...")
        self.interrupted = True

        if self.process and hasattr(self.process, 'stop'):
            try:
                self.process.stop()
            except Exception as e:
                LOGGER.error(f"Error stopping crawler process: {e}")

    def run(self) -> bool:
        """
        Run the scraper based on the specified mode.
        
        Returns:
            bool: True if successful, False otherwise
        """
        if self.args.daemon:
            return self.run_daemon()
        else:
            return self.run_once()


def parse_args() -> argparse.Namespace:
    """
    Parse command-line arguments.
    
    Returns:
        argparse.Namespace: Parsed arguments
    """
    parser = argparse.ArgumentParser(
        description='Farsiland Scraper',
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )

    # Mode selection
    mode_group = parser.add_mutually_exclusive_group()
    mode_group.add_argument('--daemon', action='store_true', 
                           help='Run the scraper continuously')

    # Spider selection
    parser.add_argument('--spiders', nargs='+', 
                       choices=['series', 'episodes', 'movies', 'all'], 
                       default=['all'], 
                       help='Spiders to run')
    
    # URL option
    parser.add_argument('--url', type=str,
                       help='Scrape a specific URL')
    
    # Cache override
    parser.add_argument('--force-refresh', action='store_true', help='Ignore cache and re-fetch all HTML')

    # Content source
    parser.add_argument('--sitemap', action='store_true',
                       help='Use parsed sitemap URLs instead of crawling site')
    parser.add_argument('--update-sitemap', action='store_true',
                       help='Update sitemap data before scraping')
    parser.add_argument('--sitemap-file', type=str,
                       help='Path to sitemap file')

    # Limits and throttling
    parser.add_argument('--limit', type=int,
                       help=f'Limit number of items to crawl per spider (default: {MAX_ITEMS_PER_CATEGORY})')
    parser.add_argument('--concurrent-requests', type=int,
                       help='Maximum concurrent requests')
    parser.add_argument('--download-delay', type=float,
                       help='Delay between requests in seconds')

    # Output options
    parser.add_argument('--export', action='store_true',
                       help='Export database to JSON after scraping')
    parser.add_argument('--export-file', type=str,
                       help='Path to export JSON file')
    parser.add_argument('--notify', action='store_true',
                       help='Notify about new content after scraping')

    # Logging options
    parser.add_argument('--verbose', action='store_true',
                       help='Enable verbose logging')
    parser.add_argument('--log-file', type=str,
                       help='Path to log file')

    return parser.parse_args()


def main() -> int:
    """
    Main entry point for the scraper.
    
    Returns:
        int: Exit code (0 for success, 1 for failure)
    """
    try:
        args = parse_args()
        manager = ScrapeManager(args)
        success = manager.run()
        return 0 if success else 1
    except Exception as e:
        LOGGER.error(f"Unhandled exception in main: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    print("Running Farsiland Scraper...")
    exit_code = main()
    print(f"Scraper {'finished successfully' if exit_code == 0 else 'encountered an error'}.")
    sys.exit(exit_code)