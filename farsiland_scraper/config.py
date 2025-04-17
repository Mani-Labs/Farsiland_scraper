# File: farsiland_scraper/config.py
# Version: 1.2.0
# Last Updated: 2025-04-17

import os
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

# Project base directories - using pathlib for cross-platform compatibility
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = Path(os.environ.get('FARSILAND_DATA_DIR', BASE_DIR / "data"))
LOG_DIR = Path(os.environ.get('FARSILAND_LOG_DIR', BASE_DIR / "logs"))
CACHE_DIR = Path(os.environ.get('FARSILAND_CACHE_DIR', BASE_DIR / "cache"))

# Ensure directories exist
DATA_DIR.mkdir(exist_ok=True, parents=True)
LOG_DIR.mkdir(exist_ok=True, parents=True)
CACHE_DIR.mkdir(exist_ok=True, parents=True)

# Target website configuration
BASE_URL = os.environ.get('FARSILAND_BASE_URL', "https://farsiland.com")
SITEMAP_URL = os.environ.get('FARSILAND_SITEMAP_URL', f"{BASE_URL}/sitemap_index.xml")
PARSED_SITEMAP_PATH = Path(os.environ.get('FARSILAND_SITEMAP_PATH', DATA_DIR / "parsed_urls.json"))

# Content zone URLs
CONTENT_ZONES = {
    "series": f"{BASE_URL}/series-22/",
    "episodes": f"{BASE_URL}/episodes-12/",
    "movies": f"{BASE_URL}/movies-2025/",
    "iranian_series": f"{BASE_URL}/iranian-series/",
    "old_movies": f"{BASE_URL}/old-iranian-movies/"
}

# Database configuration
DATABASE_PATH = Path(os.environ.get('FARSILAND_DB_PATH', DATA_DIR / "farsiland.db"))
JSON_OUTPUT_PATH = Path(os.environ.get('FARSILAND_JSON_PATH', DATA_DIR / "site_index.json"))

# Default request headers
DEFAULT_HEADERS = {
    "User-Agent": os.environ.get('FARSILAND_USER_AGENT', 
                                 "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/122.0"),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
    "Referer": BASE_URL,
    "DNT": "1",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "same-origin",
    "Sec-Fetch-User": "?1",
    "Cache-Control": "max-age=0"
}

# Request settings - configurable through environment variables
REQUEST_TIMEOUT = int(os.environ.get('FARSILAND_REQUEST_TIMEOUT', 30))  # seconds
REQUEST_RETRY_COUNT = int(os.environ.get('FARSILAND_RETRY_COUNT', 3))
REQUEST_RETRY_DELAY = int(os.environ.get('FARSILAND_RETRY_DELAY', 5))  # seconds

# Scraping settings
SCRAPE_INTERVAL = int(os.environ.get('FARSILAND_SCRAPE_INTERVAL', 600))  # 10 minutes in seconds
MAX_ITEMS_PER_CATEGORY = int(os.environ.get('FARSILAND_MAX_ITEMS', 10))  # Increased from 3 to a more reasonable value
USE_SITEMAP = os.environ.get('FARSILAND_USE_SITEMAP', 'true').lower() == 'true'  # Controls whether to rely on the sitemap

# Configure logging level from environment
LOG_LEVEL_MAP = {
    'debug': logging.DEBUG,
    'info': logging.INFO,
    'warning': logging.WARNING,
    'error': logging.ERROR,
    'critical': logging.CRITICAL
}
DEFAULT_LOG_LEVEL = LOG_LEVEL_MAP.get(os.environ.get('FARSILAND_LOG_LEVEL', 'info').lower(), logging.INFO)

def setup_logger(name, log_file, level=None):
    """
    Set up a logger with file and console handlers.
    
    Args:
        name: Logger name
        log_file: Path to log file
        level: Logging level (defaults to configured DEFAULT_LOG_LEVEL)
        
    Returns:
        Configured logger instance
    """
    if level is None:
        level = DEFAULT_LOG_LEVEL
        
    logger = logging.getLogger(name)
    logger.setLevel(level)

    # Only add handlers if they don't exist yet
    if not logger.handlers:
        # File handler with rotation
        file_handler = RotatingFileHandler(
            LOG_DIR / log_file,
            maxBytes=10*1024*1024,  # 10MB
            backupCount=5
        )
        file_formatter = logging.Formatter(
            '%(asctime)s [%(levelname)s] [%(name)s] %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        file_handler.setFormatter(file_formatter)

        # Console handler
        console_handler = logging.StreamHandler()
        console_formatter = logging.Formatter('%(asctime)s [%(levelname)s] [%(name)s] %(message)s', datefmt='%H:%M:%S')
        console_handler.setFormatter(console_formatter)

        logger.addHandler(file_handler)
        logger.addHandler(console_handler)

    return logger

# Create main logger
LOGGER = setup_logger('farsiland_scraper', 'scraper.log')