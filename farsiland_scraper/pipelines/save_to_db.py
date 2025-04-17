# File: farsiland_scraper/pipelines/save_to_db.py
# Version: 4.0.0
# Last Updated: 2025-04-19 16:00

"""
Pipeline for saving scraped items to the database.

This pipeline:
1. Handles processing of ShowItem, EpisodeItem, and MovieItem objects
2. Ensures safe database operations using parameterized queries
3. Maintains consistency between related items (e.g., show episode counts)
4. Properly manages database transactions
"""

import json
from datetime import datetime
from typing import Dict, List, Any, Optional, Union, Tuple, cast
from farsiland_scraper.database.models import Database
from farsiland_scraper.items import ShowItem, EpisodeItem, MovieItem
from farsiland_scraper.config import LOGGER
import scrapy

class SaveToDatabasePipeline:
    """
    Pipeline for saving scraped items to the database.
    
    This pipeline processes the three main item types:
    - ShowItem: TV shows/series
    - EpisodeItem: Individual episodes of TV shows
    - MovieItem: Movies
    
    Each item type has its own processing method with appropriate validation
    and database operations.
    """

    def __init__(self):
        """Initialize the pipeline with a null database connection."""
        self.db = None

    def open_spider(self, spider: scrapy.Spider) -> None:
        """
        Initialize database connection when the spider starts.
        
        Args:
            spider: The spider that was opened
        """
        LOGGER.info("========== DATABASE PIPELINE ACTIVATED ==========")
        try:
            self.db = Database()
            LOGGER.info("Database connection initialized")
        except Exception as e:
            LOGGER.error(f"Failed to initialize database connection: {e}")
            raise

    def close_spider(self, spider: scrapy.Spider) -> None:
        """
        Clean up database connection when the spider finishes.
        
        Args:
            spider: The spider that was closed
        """
        if self.db:
            try:
                # Export to JSON if configured
                if hasattr(spider, 'export_json') and spider.export_json:
                    self.db.export_to_json()
                    
                self.db.close()
                LOGGER.info("Database connection closed")
            except Exception as e:
                LOGGER.error(f"Error closing database connection: {e}")

    def process_item(self, item: Union[ShowItem, EpisodeItem, MovieItem], spider: scrapy.Spider) -> Union[ShowItem, EpisodeItem, MovieItem]:
        """
        Process an item and save it to the database.
        
        This method routes items to type-specific processing methods.
        
        Args:
            item: The item to save
            spider: The spider that scraped the item
            
        Returns:
            The processed item
        """
        try:
            if isinstance(item, ShowItem):
                return self._process_show(item)
            elif isinstance(item, EpisodeItem):
                return self._process_episode(item)
            elif isinstance(item, MovieItem):
                return self._process_movie(item)
            else:
                LOGGER.warning(f"Unknown item type: {type(item).__name__}")
            
            return item
        except Exception as e:
            LOGGER.error(f"Error processing item: {e}", exc_info=True)
            return item

    def _process_show(self, item: ShowItem) -> ShowItem:
        """
        Process and save a show item to the database.
        
        Args:
            item: The show item to save
            
        Returns:
            The processed show item
        """
        if not self.db:
            LOGGER.error("Database connection not initialized")
            return item
            
        try:
            show_url = item.get('url')
            if not show_url:
                LOGGER.error("Cannot process show without URL")
                return item
                
            LOGGER.debug(f"Processing show: {item.get('title_en', show_url)}")
            show_data = dict(item)

            # Convert lists to JSON strings
            json_fields = ["genres", "directors", "cast", "seasons"]
            for field in json_fields:
                if field in show_data and isinstance(show_data[field], list):
                    show_data[field] = json.dumps(show_data[field])

            # Check for update: compare lastmod from sitemap with DB record
            is_new = 1  # Default to treating as new
            
            # Use parameterized query
            existing = self.db.fetchone(
                "SELECT lastmod, is_new FROM shows WHERE url=?", 
                [show_data.get("url")]
            )
            
            if existing is not None:
                db_lastmod = existing["lastmod"]
                # If the sitemap's lastmod differs, mark as new
                if db_lastmod != show_data.get("lastmod"):
                    is_new = 1
                else:
                    # Keep existing is_new status if lastmod hasn't changed
                    is_new = existing["is_new"]
            
            show_data["is_new"] = is_new
            show_data["last_scraped"] = datetime.utcnow().isoformat()

            # Prepare columns and values for SQL INSERT
            columns = (
                "url", "sitemap_url", "title_en", "title_fa", "poster",
                "description", "first_air_date", "rating", "rating_count",
                "season_count", "episode_count", "genres", "directors", "cast",
                "social_shares", "comments_count", "seasons", "is_new", "lastmod", "last_scraped"
            )
            
            # Build SQL using parameters
            placeholders = ", ".join("?" * len(columns))
            sql = f"INSERT OR REPLACE INTO shows ({', '.join(columns)}) VALUES ({placeholders})"
            
            # Extract values in the same order as columns
            values = tuple(show_data.get(col) for col in columns)
            
            # Execute the query with proper parameters
            self.db.execute(sql, values)
            self.db.commit()
            
            LOGGER.info(f"Saved show: {item.get('title_en', show_url)}")
            return item
            
        except Exception as e:
            LOGGER.error(f"Error saving show {item.get('url', '')}: {e}")
            if self.db:
                self.db.rollback()
            return item

    def _process_episode(self, item: EpisodeItem) -> EpisodeItem:
        """
        Process and save an episode item to the database.
        
        Args:
            item: The episode item to save
            
        Returns:
            The processed episode item
        """
        if not self.db:
            LOGGER.error("Database connection not initialized")
            return item
            
        try:
            episode_url = item.get('url')
            if not episode_url:
                LOGGER.error("Cannot process episode without URL")
                return item
                
            LOGGER.debug(f"Processing episode: {item.get('title', episode_url)}")
            ep_data = dict(item)

            # Convert video_files list to JSON
            if "video_files" in ep_data and isinstance(ep_data["video_files"], list):
                ep_data["video_files"] = json.dumps(ep_data["video_files"])

            # Check if this is a new or updated episode
            is_new = 1  # Default to treating as new
            
            # Use parameterized query
            existing = self.db.fetchone(
                "SELECT lastmod, is_new FROM episodes WHERE url=?", 
                [ep_data.get("url")]
            )
            
            if existing is not None:
                db_lastmod = existing["lastmod"]
                # If the lastmod has changed, mark as new
                if db_lastmod != ep_data.get("lastmod"):
                    is_new = 1
                else:
                    # Keep existing is_new status if lastmod hasn't changed
                    is_new = existing["is_new"]
            
            ep_data["is_new"] = is_new
            ep_data["last_scraped"] = datetime.utcnow().isoformat()

            # Prepare columns and values for SQL INSERT
            columns = (
                "url", "sitemap_url", "show_url", "season_number", "episode_number",
                "title", "air_date", "thumbnail", "video_files", "is_new", 
                "lastmod", "last_scraped"
            )
            
            # Build SQL using parameters
            placeholders = ", ".join("?" * len(columns))
            sql = f"INSERT OR REPLACE INTO episodes ({', '.join(columns)}) VALUES ({placeholders})"
            
            # Extract values in the same order as columns
            values = tuple(ep_data.get(col) for col in columns)
            
            # Execute the query with proper parameters
            self.db.execute(sql, values)
            self.db.commit()
            
            # Update the show's episode count
            show_url = ep_data.get("show_url")
            if show_url:
                self._update_show_episode_count(show_url)
            
            LOGGER.info(f"Saved episode: {item.get('title', episode_url)}")
            return item
            
        except Exception as e:
            LOGGER.error(f"Error saving episode {item.get('url', '')}: {e}")
            if self.db:
                self.db.rollback()
            return item

    def _process_movie(self, item: MovieItem) -> MovieItem:
        """
        Process and save a movie item to the database.
        
        Args:
            item: The movie item to save
            
        Returns:
            The processed movie item
        """
        if not self.db:
            LOGGER.error("Database connection not initialized")
            return item
            
        try:
            movie_url = item.get('url')
            if not movie_url:
                LOGGER.error("Cannot process movie without URL")
                return item
                
            LOGGER.debug(f"Processing movie: {item.get('title_en', movie_url)}")
            movie_data = dict(item)

            # Convert list fields to JSON
            json_fields = ["genres", "directors", "cast", "video_files"]
            for field in json_fields:
                if field in movie_data and isinstance(movie_data[field], list):
                    movie_data[field] = json.dumps(movie_data[field])

            # Check if this is a new or updated movie
            is_new = 1  # Default to treating as new
            
            # Use parameterized query
            existing = self.db.fetchone(
                "SELECT lastmod, is_new FROM movies WHERE url=?", 
                [movie_data.get("url")]
            )
            
            if existing is not None:
                db_lastmod = existing["lastmod"]
                # If the lastmod has changed, mark as new
                if db_lastmod != movie_data.get("lastmod"):
                    is_new = 1
                else:
                    # Keep existing is_new status if lastmod hasn't changed
                    is_new = existing["is_new"]
            
            movie_data["is_new"] = is_new
            movie_data["last_scraped"] = datetime.utcnow().isoformat()

            # Prepare columns and values for SQL INSERT
            columns = (
                "url", "sitemap_url", "title_en", "title_fa", "poster",
                "description", "release_date", "year", "rating", "rating_count",
                "genres", "directors", "cast", "social_shares", "comments_count",
                "video_files", "is_new", "lastmod", "last_scraped"
            )
            
            # Build SQL using parameters
            placeholders = ", ".join("?" * len(columns))
            sql = f"INSERT OR REPLACE INTO movies ({', '.join(columns)}) VALUES ({placeholders})"
            
            # Extract values in the same order as columns
            values = tuple(movie_data.get(col) for col in columns)
            
            # Execute the query with proper parameters
            self.db.execute(sql, values)
            self.db.commit()
            
            LOGGER.info(f"Saved movie: {item.get('title_en', movie_url)}")
            return item
            
        except Exception as e:
            LOGGER.error(f"Error saving movie {item.get('url', '')}: {e}")
            if self.db:
                self.db.rollback()
            return item
        
    def _update_show_episode_count(self, show_url: str) -> None:
        """
        Update the episode count for a show based on actual episodes in database.
        
        This method is more efficient by using a single query and transaction.
        
        Args:
            show_url: The URL of the show to update
        """
        if not self.db or not show_url:
            return
            
        try:
            # Begin a transaction
            self.db.execute("BEGIN TRANSACTION")
            
            # Count episodes for this show in a single query
            result = self.db.fetchone(
                "SELECT COUNT(*) as count FROM episodes WHERE show_url=?",
                [show_url]
            )
            
            if result and "count" in result:
                episode_count = result["count"]
                
                # Update the show with the new count
                self.db.execute(
                    "UPDATE shows SET episode_count=? WHERE url=?",
                    (episode_count, show_url)
                )
                
                # Commit the transaction
                self.db.commit()
                LOGGER.debug(f"Updated episode count for {show_url}: {episode_count}")
            else:
                self.db.rollback()
                LOGGER.warning(f"Failed to count episodes for {show_url}")
                
        except Exception as e:
            LOGGER.error(f"Error updating episode count for {show_url}: {e}")
            if self.db:
                self.db.rollback()