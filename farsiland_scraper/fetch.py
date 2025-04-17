# File: farsiland_scraper/fetch.py
# Version: 1.1.0
# Last Updated: 2025-04-24

"""
Utility functions for fetching and caching web pages.

Changelog:
- [1.0.1] Added detailed error logging and traceback for fetch failures
- [1.1.0] Fixed file handle leaks in error cases
- [1.1.0] Removed forced DEBUG log level
- [1.1.0] Added simple file locking for cache access
- [1.1.0] Made timeout and retry parameters configurable from config
"""

import os
import hashlib
import aiohttp
import logging
import asyncio
import traceback
import filelock
from pathlib import Path
from typing import Optional
from datetime import datetime

from farsiland_scraper.config import (
    CACHE_DIR, 
    LOGGER, 
    REQUEST_TIMEOUT, 
    REQUEST_RETRY_COUNT, 
    REQUEST_RETRY_DELAY
)

CACHE_BASE = Path(CACHE_DIR) / "pages"

def slugify_url(url: str) -> str:
    """
    Convert a URL to a safe filename.
    
    Args:
        url: The URL to convert
        
    Returns:
        A safe filename generated from the URL
    """
    slug = url.strip("/").replace("https://", "").replace("http://", "")
    return slug.replace("/", "-")

def get_cache_path(url: str, content_type: str) -> Path:
    """
    Get the cache file path for a URL.
    
    Args:
        url: The URL to cache
        content_type: The type of content (e.g., 'movies', 'episodes')
        
    Returns:
        The path to the cache file
    """
    filename = slugify_url(url) + ".html"
    return CACHE_BASE / content_type / filename

def get_lock_path(cache_path: Path) -> Path:
    """
    Get the lock file path for a cache file.
    
    Args:
        cache_path: The path to the cache file
        
    Returns:
        The path to the lock file
    """
    return cache_path.with_suffix(cache_path.suffix + ".lock")

async def fetch_and_cache(
    url: str, 
    content_type: str, 
    lastmod: Optional[str] = None, 
    force_refresh: bool = False,
    timeout: int = None,
    retries: int = None
) -> Optional[str]:
    """
    Fetch a URL and cache the result.
    
    Args:
        url: The URL to fetch
        content_type: The type of content
        lastmod: Last modification timestamp from sitemap
        force_refresh: Whether to force a refresh regardless of cache
        timeout: Request timeout in seconds (defaults to config value)
        retries: Number of retry attempts (defaults to config value)
        
    Returns:
        The HTML content or None if fetching failed
    """
    # Use config values if not specified
    if timeout is None:
        timeout = REQUEST_TIMEOUT
    if retries is None:
        retries = REQUEST_RETRY_COUNT
    
    cache_path = get_cache_path(url, content_type)
    lock_path = get_lock_path(cache_path)
    
    # Create parent directories if they don't exist
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Use a lock to prevent concurrent access to the same cache file
    lock = filelock.FileLock(str(lock_path))
    
    try:
        with lock.acquire(timeout=10):  # Wait up to 10 seconds for the lock
            # Check if cache exists and is valid
            if cache_path.exists() and not force_refresh:
                if lastmod:
                    try:
                        cache_time = datetime.fromtimestamp(cache_path.stat().st_mtime)
                        lastmod_time = datetime.fromisoformat(lastmod)
                        if cache_time >= lastmod_time:
                            LOGGER.info(f"Using cached version of {url}")
                            with open(cache_path, 'r', encoding='utf-8') as f:
                                return f.read()
                    except Exception as e:
                        LOGGER.warning(f"Could not compare lastmod for {url}: {e}")
                        with open(cache_path, 'r', encoding='utf-8') as f:
                            return f.read()
                else:
                    with open(cache_path, 'r', encoding='utf-8') as f:
                        return f.read()

            # If cache doesn't exist or is invalid, fetch the URL
            for attempt in range(retries):
                try:
                    async with aiohttp.ClientSession() as session:
                        async with session.get(url, timeout=timeout) as response:
                            if response.status == 200:
                                html = await response.text()
                                # Write to cache
                                with open(cache_path, 'w', encoding='utf-8') as f:
                                    f.write(html)
                                LOGGER.info(f"Fetched and cached {url}")
                                return html
                            else:
                                LOGGER.warning(f"Failed to fetch {url} (status: {response.status})")
                                # Don't retry for client errors (4xx)
                                if 400 <= response.status < 500:
                                    break
                except asyncio.TimeoutError:
                    LOGGER.warning(f"Timeout fetching {url} (attempt {attempt+1}/{retries})")
                except Exception as e:
                    LOGGER.error(f"[FETCH FAIL] Error fetching {url}: {e}")
                    LOGGER.debug(traceback.format_exc())
                
                # If we're not on the last attempt, wait before retrying
                if attempt < retries - 1:
                    await asyncio.sleep(REQUEST_RETRY_DELAY * (attempt + 1))  # Exponential backoff
            
            # If we get here, all retry attempts failed
            return None
    except filelock.Timeout:
        LOGGER.warning(f"Could not acquire lock for {url}, cache file may be in use")
        # Try to use the cached version anyway if it exists
        if cache_path.exists():
            try:
                with open(cache_path, 'r', encoding='utf-8') as f:
                    return f.read()
            except Exception as e:
                LOGGER.error(f"Error reading cache file after lock timeout: {e}")
        return None
    except Exception as e:
        LOGGER.error(f"Unexpected error in fetch_and_cache for {url}: {e}")
        return None

# Synchronous wrapper for use in blocking code
def fetch_sync(
    url: str, 
    content_type: str, 
    lastmod: Optional[str] = None, 
    force_refresh: bool = False,
    timeout: int = None,
    retries: int = None
) -> Optional[str]:
    """
    Synchronous version of fetch_and_cache.
    
    Args:
        url: The URL to fetch
        content_type: The type of content
        lastmod: Last modification timestamp from sitemap
        force_refresh: Whether to force a refresh regardless of cache
        timeout: Request timeout in seconds (defaults to config value)
        retries: Number of retry attempts (defaults to config value)
        
    Returns:
        The HTML content or None if fetching failed
    """
    return asyncio.run(
        fetch_and_cache(
            url, 
            content_type, 
            lastmod, 
            force_refresh,
            timeout,
            retries
        )
    )