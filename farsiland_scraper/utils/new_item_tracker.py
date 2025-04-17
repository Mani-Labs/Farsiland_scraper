# File: farsiland_scraper/utils/new_item_tracker.py
# Version: 2.0.0
# Last Updated: 2025-04-17 12:00

"""
Utility for tracking and processing new content.

Handles:
- Fetching new items from the database
- Tracking processed URLs to avoid duplicates
- Notifying external systems about new content
- Atomic file operations for data integrity
"""

import json
import os
import shutil
import tempfile
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Set, Any, Optional

from farsiland_scraper.config import LOGGER, JSON_OUTPUT_PATH


class NewItemTracker:
    """
    Utility for tracking and processing new content.
    
    Provides methods to:
    - Get content marked as new in the database
    - Track which URLs have already been processed
    - Mark content as processed
    - Notify external systems about new content
    """

    def __init__(self, db):
        """
        Initialize the new item tracker with a database connection.
        
        Args:
            db: Database instance with connection to the SQLite database
        """
        self.db = db
        # Ensure the parent directory exists
        cache_dir = Path(JSON_OUTPUT_PATH).parent
        cache_dir.mkdir(exist_ok=True, parents=True)
        
        self.cache_file = Path(cache_dir, "processed_urls.json")
        self.processed_urls = self._load_processed_urls()
        
        LOGGER.debug(f"NewItemTracker initialized with cache file: {self.cache_file}")

    def _load_processed_urls(self) -> Dict[str, Set[str]]:
        """
        Load the previously processed URLs from the cache file.
        
        Returns:
            Dictionary mapping content types to sets of processed URLs
        """
        result = {
            "shows": set(),
            "episodes": set(),
            "movies": set()
        }

        if not self.cache_file.exists():
            LOGGER.info(f"Cache file not found at {self.cache_file}, using empty cache")
            return result

        try:
            with open(self.cache_file, 'r', encoding='utf-8') as f:
                data = json.load(f)

                # Convert lists to sets for faster lookup
                for content_type in result:
                    if content_type in data and isinstance(data[content_type], list):
                        result[content_type] = set(data[content_type])

            LOGGER.info(
                f"Loaded {sum(len(urls) for urls in result.values())} processed URLs from cache"
            )

        except json.JSONDecodeError as e:
            LOGGER.error(f"Invalid JSON in cache file: {e}")
            # Create a backup of the corrupt file
            backup_path = f"{self.cache_file}.bak.{datetime.now().strftime('%Y%m%d%H%M%S')}"
            try:
                shutil.copy2(self.cache_file, backup_path)
                LOGGER.info(f"Created backup of corrupt cache file at {backup_path}")
            except Exception as backup_err:
                LOGGER.error(f"Failed to create backup of corrupt cache file: {backup_err}")
        
        except (IOError, OSError) as e:
            LOGGER.error(f"Error reading cache file: {e}")

        return result

    def _save_processed_urls(self) -> bool:
        """
        Save the processed URLs to the cache file using atomic file operations.
        
        Returns:
            True if successful, False otherwise
        """
        try:
            # Convert sets to lists for JSON serialization
            data = {
                content_type: list(urls)
                for content_type, urls in self.processed_urls.items()
            }

            # Create a temporary file in the same directory
            temp_dir = self.cache_file.parent
            temp_dir.mkdir(exist_ok=True, parents=True)
            
            with tempfile.NamedTemporaryFile(mode='w', 
                                             dir=temp_dir,
                                             delete=False,
                                             suffix='.json') as tf:
                # Write to the temporary file
                json.dump(data, tf, ensure_ascii=False, indent=2)
                temp_path = tf.name
            
            # Atomic replace - this is an atomic operation on most modern file systems
            shutil.move(temp_path, self.cache_file)

            LOGGER.info(
                f"Saved {sum(len(urls) for urls in self.processed_urls.values())} processed URLs to cache"
            )
            return True

        except Exception as e:
            LOGGER.error(f"Error saving processed URLs to cache: {e}")
            # Clean up temporary file if it exists
            if 'temp_path' in locals():
                try:
                    os.unlink(temp_path)
                except:
                    pass
            return False

    def _fetch_all_new_content(self) -> Dict[str, List[Dict[str, Any]]]:
        """
        Fetch items from shows, episodes, and movies where is_new=1.
        
        Returns:
            Dictionary with keys: shows, episodes, movies, each containing a list of items
        """
        result = {
            "shows": [],
            "episodes": [],
            "movies": []
        }
        
        try:
            # Fetch new shows
            rows = self.db.fetchall("SELECT * FROM shows WHERE is_new=1")
            result["shows"] = [dict(row) for row in rows] if rows else []
            
            # Fetch new episodes
            rows = self.db.fetchall("SELECT * FROM episodes WHERE is_new=1")
            result["episodes"] = [dict(row) for row in rows] if rows else []
            
            # Fetch new movies
            rows = self.db.fetchall("SELECT * FROM movies WHERE is_new=1")
            result["movies"] = [dict(row) for row in rows] if rows else []
            
        except Exception as e:
            LOGGER.error(f"Database error fetching new content: {e}")
        
        return result

    def get_new_content(self) -> Dict[str, List[Dict]]:
        """
        Get all content marked as new that hasn't been processed yet.
        
        Returns:
            Dictionary with content types as keys and lists of items as values
        """
        # First, fetch all new content from the database
        new_content = self._fetch_all_new_content()

        # Filter out content that's already been processed
        filtered_content = {}
        
        for content_type, items in new_content.items():
            # Create a new list with only unprocessed items
            filtered_items = []
            processed_urls = self.processed_urls.get(content_type, set())
            
            for item in items:
                url = item.get("url")
                if url and url not in processed_urls:
                    filtered_items.append(item)
            
            filtered_content[content_type] = filtered_items

        # Log summary of findings
        for content_type, items in filtered_content.items():
            LOGGER.info(f"Found {len(items)} new {content_type}")

        return filtered_content

    def mark_as_processed(self, content: Dict[str, List[Dict]]) -> bool:
        """
        Mark content as processed in both database and local cache.
        
        Args:
            content: Dictionary mapping content types to lists of items
            
        Returns:
            True if successful, False otherwise
        """
        if not content or not any(items for items in content.values()):
            LOGGER.debug("No content to mark as processed")
            return True
            
        success = True
        
        try:
            # Process each content type
            for content_type, items in content.items():
                if not items:
                    continue
                    
                # Extract IDs for database update
                ids = [item.get("id") for item in items if item.get("id")]
                if not ids:
                    continue
                    
                # Update database first
                db_success = self._mark_as_processed_in_db(content_type, ids)
                if not db_success:
                    LOGGER.error(f"Failed to mark {content_type} as processed in database")
                    success = False
                    continue
                
                # Then update the URL cache
                urls = [item.get("url") for item in items if item.get("url")]
                if urls:
                    # Get the appropriate set or create a new one
                    url_set = self.processed_urls.get(content_type, set())
                    url_set.update(urls)
                    self.processed_urls[content_type] = url_set
            
            # Save the updated URL cache
            if success:
                cache_success = self._save_processed_urls()
                if not cache_success:
                    LOGGER.warning("Changes were committed to database but failed to update URL cache")
                    success = False
                    
            return success
            
        except Exception as e:
            LOGGER.error(f"Unexpected error marking content as processed: {e}")
            return False

    def _mark_as_processed_in_db(self, content_type: str, ids: List[int]) -> bool:
        """
        Mark content as processed in the database.
        
        Args:
            content_type: Type of content ('shows', 'episodes', 'movies')
            ids: List of item IDs to mark as processed
            
        Returns:
            True if successful, False otherwise
        """
        if not ids:
            return True
            
        try:
            # Map content types to table names
            table_map = {
                'shows': 'shows',
                'series': 'shows',  # Allow 'series' to map to 'shows' table for compatibility
                'episodes': 'episodes',
                'movies': 'movies'
            }
            
            if content_type not in table_map:
                LOGGER.error(f"Invalid content type: {content_type}")
                return False
                
            table = table_map[content_type]
            
            # Use the method from the database class
            return self.db.mark_content_as_processed(content_type, ids)
            
        except Exception as e:
            LOGGER.error(f"Error marking {content_type} as processed in database: {e}")
            return False

    def notify_new_content(self, content: Dict[str, List[Dict]]) -> bool:
        """
        Notify external systems about new content.
        
        Args:
            content: Dictionary mapping content types to lists of items
            
        Returns:
            True if successfully notified, False otherwise
        """
        if not content or not any(items for items in content.values()):
            LOGGER.info("No new content to notify about")
            return True

        try:
            # Generate a notification file
            notify_dir = Path(JSON_OUTPUT_PATH).parent
            notify_dir.mkdir(exist_ok=True, parents=True)
            
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            notify_file = Path(notify_dir, f"new_content_{timestamp}.json")

            # Prepare notification data with summary
            summary = {content_type: len(items) for content_type, items in content.items()}
            
            notify_data = {
                "timestamp": datetime.now().isoformat(),
                "summary": summary,
                "content": content
            }

            # Write to file using atomic operations
            with tempfile.NamedTemporaryFile(mode='w', 
                                            dir=notify_dir,
                                            delete=False,
                                            suffix='.json') as tf:
                json.dump(notify_data, tf, ensure_ascii=False, indent=2)
                temp_path = tf.name
            
            # Atomic replace
            shutil.move(temp_path, notify_file)

            LOGGER.info(f"Notification file created at {notify_file}")
            
            # Implementation extension points for other notification methods:
            # 1. Webhook to external system
            # 2. Email notification
            # 3. Push notification
            # 4. External API call

            return True

        except Exception as e:
            LOGGER.error(f"Error notifying about new content: {e}")
            # Clean up temporary file if it exists
            if 'temp_path' in locals():
                try:
                    os.unlink(temp_path)
                except:
                    pass
            return False

    def get_stats(self) -> Dict[str, Any]:
        """
        Get statistics about tracked URLs.
        
        Returns:
            Dictionary with statistics about processed URLs
        """
        stats = {
            "processed_url_counts": {
                content_type: len(urls) 
                for content_type, urls in self.processed_urls.items()
            },
            "cache_file": str(self.cache_file),
            "cache_file_exists": self.cache_file.exists(),
            "cache_file_size": self.cache_file.stat().st_size if self.cache_file.exists() else 0,
            "timestamp": datetime.now().isoformat()
        }
        
        return stats