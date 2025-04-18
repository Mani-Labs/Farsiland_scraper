# File: farsiland_scraper/database/models.py
# Version: 3.4.0
# Last Updated: 2025-04-23

"""
Changelog:
- Added missing mark_content_as_processed() method
- Fixed SQL injection vulnerabilities by using parameterized queries
- Improved _load_table_with_json_fields implementation
- Added robust error handling for database operations
- Added basic transaction handling for database operations
"""

import sqlite3
import json
import os
import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional, Union, Tuple
from farsiland_scraper.config import DATABASE_PATH, JSON_OUTPUT_PATH, LOGGER

class Database:
    def __init__(self, db_path: str = DATABASE_PATH):
        """
        Initialize the database connection.
        
        Args:
            db_path: Path to the SQLite database file
        """
        self.db_path = str(db_path)
        self.conn = None
        self.cursor = None
        
        try:
            # Ensure database directory exists
            os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
            
            # Connect to the database
            self.conn = sqlite3.connect(self.db_path)
            self.conn.row_factory = sqlite3.Row
            self.cursor = self.conn.cursor()
            
            # Create tables if they don't exist
            self._create_tables()
        except sqlite3.Error as e:
            LOGGER.error(f"Database initialization error: {e}")
            raise

    def _create_tables(self):
        """Create database tables if they don't exist."""
        try:
            self.cursor.execute("""
                CREATE TABLE IF NOT EXISTS movies (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    url TEXT UNIQUE NOT NULL,
                    sitemap_url TEXT,
                    title_en TEXT,
                    title_fa TEXT,
                    poster TEXT,
                    description TEXT,
                    release_date TEXT,
                    year INTEGER,
                    rating REAL,
                    rating_count INTEGER,
                    genres TEXT,
                    directors TEXT,
                    cast TEXT,
                    social_shares INTEGER,
                    comments_count INTEGER,
                    video_files TEXT,
                    is_new INTEGER DEFAULT 1,
                    lastmod TEXT,
                    last_scraped TEXT,
                    cached_at TEXT,
                    source TEXT
                )
            """)

            self.cursor.execute("""
                CREATE TABLE IF NOT EXISTS shows (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    url TEXT UNIQUE NOT NULL,
                    sitemap_url TEXT,
                    title_en TEXT,
                    title_fa TEXT,
                    poster TEXT,
                    description TEXT,
                    first_air_date TEXT,
                    rating REAL,
                    rating_count INTEGER,
                    season_count INTEGER,
                    episode_count INTEGER,
                    genres TEXT,
                    directors TEXT,
                    cast TEXT,
                    social_shares INTEGER,
                    comments_count INTEGER,
                    seasons TEXT,
                    is_new INTEGER DEFAULT 1,
                    lastmod TEXT,
                    last_scraped TEXT,
                    cached_at TEXT,
                    source TEXT
                )
            """)

            self.cursor.execute("""
                CREATE TABLE IF NOT EXISTS episodes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    url TEXT UNIQUE NOT NULL,
                    sitemap_url TEXT,
                    show_url TEXT,
                    season_number INTEGER,
                    episode_number INTEGER,
                    title TEXT,
                    air_date TEXT,
                    thumbnail TEXT,
                    video_files TEXT,
                    is_new INTEGER DEFAULT 1,
                    lastmod TEXT,
                    last_scraped TEXT,
                    cached_at TEXT,
                    source TEXT,
                    FOREIGN KEY (show_url) REFERENCES shows(url)
                )
            """)

            indexes = [
                "CREATE INDEX IF NOT EXISTS idx_shows_url ON shows(url)",
                "CREATE INDEX IF NOT EXISTS idx_movies_url ON movies(url)",
                "CREATE INDEX IF NOT EXISTS idx_episodes_url ON episodes(url)",
                "CREATE INDEX IF NOT EXISTS idx_episodes_show_url ON episodes(show_url)",
                "CREATE INDEX IF NOT EXISTS idx_episodes_season_ep ON episodes(season_number, episode_number)",
                "CREATE INDEX IF NOT EXISTS idx_episodes_show_season_ep ON episodes(show_url, season_number, episode_number)"
            ]

            for index in indexes:
                self.cursor.execute(index)

            self.conn.commit()
        except sqlite3.Error as e:
            LOGGER.error(f"Error creating tables: {e}")
            if self.conn:
                self.conn.rollback()
            raise

    def execute(self, query: str, params: Union[tuple, list, dict] = ()) -> sqlite3.Cursor:
        """
        Execute an SQL query with parameters.
        
        Args:
            query: SQL query string
            params: Query parameters
            
        Returns:
            SQLite cursor
            
        Raises:
            sqlite3.Error: If there's a database error
        """
        try:
            return self.cursor.execute(query, params)
        except sqlite3.Error as e:
            LOGGER.error(f"SQL execution error: {e}")
            LOGGER.error(f"Query: {query}")
            LOGGER.error(f"Params: {params}")
            raise

    def executemany(self, query: str, params_list: List[Union[tuple, list, dict]]) -> sqlite3.Cursor:
        """
        Execute an SQL query with multiple parameter sets.
        
        Args:
            query: SQL query string
            params_list: List of parameter sets
            
        Returns:
            SQLite cursor
            
        Raises:
            sqlite3.Error: If there's a database error
        """
        try:
            return self.cursor.executemany(query, params_list)
        except sqlite3.Error as e:
            LOGGER.error(f"SQL executemany error: {e}")
            LOGGER.error(f"Query: {query}")
            raise

    def commit(self) -> None:
        """Commit the current transaction."""
        try:
            if self.conn:
                self.conn.commit()
        except sqlite3.Error as e:
            LOGGER.error(f"Commit error: {e}")
            raise

    def rollback(self) -> None:
        """Roll back the current transaction."""
        try:
            if self.conn:
                self.conn.rollback()
        except sqlite3.Error as e:
            LOGGER.error(f"Rollback error: {e}")
            pass  # We don't raise here since rollback is usually called in exception handlers

    def fetchall(self, query: str, params: Union[tuple, list, dict] = ()) -> List[sqlite3.Row]:
        """
        Execute a query and fetch all results.
        
        Args:
            query: SQL query string
            params: Query parameters
            
        Returns:
            List of rows
            
        Raises:
            sqlite3.Error: If there's a database error
        """
        try:
            return self.cursor.execute(query, params).fetchall()
        except sqlite3.Error as e:
            LOGGER.error(f"fetchall error: {e}")
            LOGGER.error(f"Query: {query}")
            LOGGER.error(f"Params: {params}")
            raise

    def fetchone(self, query: str, params: Union[tuple, list, dict] = ()) -> Optional[sqlite3.Row]:
        """
        Execute a query and fetch one result.
        
        Args:
            query: SQL query string
            params: Query parameters
            
        Returns:
            One row or None
            
        Raises:
            sqlite3.Error: If there's a database error
        """
        try:
            return self.cursor.execute(query, params).fetchone()
        except sqlite3.Error as e:
            LOGGER.error(f"fetchone error: {e}")
            LOGGER.error(f"Query: {query}")
            LOGGER.error(f"Params: {params}")
            raise

    def close(self) -> None:
        """Close the database connection."""
        if hasattr(self, 'conn') and self.conn:
            try:
                self.conn.close()
            except sqlite3.Error as e:
                LOGGER.error(f"Error closing database connection: {e}")

    def __enter__(self) -> 'Database':
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        """Context manager exit."""
        self.close()

    def get_related_episodes(self, show_url: str) -> List[Dict]:
        """
        Get all episodes related to a show.
        
        Args:
            show_url: URL of the show
            
        Returns:
            List of episode dictionaries
        """
        try:
            episodes = self.fetchall(
                "SELECT * FROM episodes WHERE show_url = ? ORDER BY season_number, episode_number", 
                (show_url,)
            )
            
            result = []
            for episode in episodes:
                ep_dict = dict(episode)
                for field in ['video_files']:
                    if field in ep_dict and ep_dict[field]:
                        try:
                            ep_dict[field] = json.loads(ep_dict[field])
                        except json.JSONDecodeError:
                            LOGGER.warning(f"Failed to parse JSON in {field} for episode {ep_dict.get('url')}")
                            ep_dict[field] = []
                result.append(ep_dict)
            return result
        except sqlite3.Error as e:
            LOGGER.error(f"Error getting related episodes: {e}")
            return []

    def mark_content_as_processed(self, content_type: str, ids: List[int]) -> bool:
        """
        Mark content items as processed (is_new=0).
        
        Args:
            content_type: Type of content ('shows', 'episodes', 'movies')
            ids: List of item IDs
            
        Returns:
            True if successful, False otherwise
        """
        if not ids:
            return True
            
        try:
            # Map content types to table names
            table_map = {
                'shows': 'shows',
                'series': 'shows',  # Allow 'series' to map to 'shows' table
                'episodes': 'episodes',
                'movies': 'movies'
            }
            
            table = table_map.get(content_type)
            if not table:
                LOGGER.error(f"Invalid content type: {content_type}")
                return False
                
            # Prepare placeholders for the IN clause
            placeholders = ', '.join(['?'] * len(ids))
            
            # Update the records
            query = f"UPDATE {table} SET is_new = 0 WHERE id IN ({placeholders})"
            self.execute(query, ids)
            self.commit()
            
            LOGGER.info(f"Marked {len(ids)} {content_type} as processed")
            return True
        except sqlite3.Error as e:
            LOGGER.error(f"Error marking content as processed: {e}")
            self.rollback()
            return False

    def export_to_json(self, output_path: Optional[str] = None, pretty: bool = True) -> bool:
        """
        Export database contents to a JSON file.
        
        Args:
            output_path: Path to save the JSON file
            pretty: Whether to format the JSON with indentation
            
        Returns:
            True if successful, False otherwise
        """
        if output_path is None:
            output_path = str(JSON_OUTPUT_PATH)

        try:
            # Ensure output directory exists
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            
            # Prepare metadata
            data = {
                "metadata": {
                    "exported_at": datetime.datetime.now().isoformat(),
                    "version": "3.5.0"
                }
            }

            # Count records in each table
            for table in ['movies', 'shows', 'episodes']:
                count = self.fetchone(f"SELECT COUNT(*) as count FROM {table}")
                data[f"{table}_count"] = count['count'] if count else 0

            # Load and process data from each table
            data['movies'] = self._load_table_with_json_fields('movies', ['genres', 'directors', 'cast', 'video_files'])
            all_episodes = self._load_table_with_json_fields('episodes', ['video_files'])

            # Create a lookup map for episodes by show_url
            show_episodes_map = {}
            for ep in all_episodes:
                show_url = ep.get('show_url')
                if show_url:
                    # Standardize URLs for consistent matching
                    show_url = show_url.rstrip('/')
                    if show_url not in show_episodes_map:
                        show_episodes_map[show_url] = []
                    show_episodes_map[show_url].append(ep)

            # Process shows and add related episodes
            shows = self._load_table_with_json_fields('shows', ['genres', 'directors', 'cast', 'seasons'])
            for show in shows:
                # Standardize URL for matching
                show_url = show.get('url', '').rstrip('/')
                
                # Get episodes for this show
                related_eps = show_episodes_map.get(show_url, [])
                
                # Log relationship info for debugging
                LOGGER.debug(f"Show: {show.get('title_en')} ({show_url}) has {len(related_eps)} related episodes")
                
                # Organize episodes by season
                seasons_map = {}
                for ep in related_eps:
                    season_num = ep.get('season_number', 0)
                    if season_num not in seasons_map:
                        seasons_map[season_num] = []
                    seasons_map[season_num].append(ep)
                    
                # Format seasons data
                final_seasons = []
                for season_num in sorted(seasons_map.keys()):
                    episodes = seasons_map[season_num]
                    
                    # Format episodes data
                    final_episodes = []
                    for ep in sorted(episodes, key=lambda x: x.get('episode_number', 0)):
                        final_episodes.append({
                            "episode_number": ep.get('episode_number'),
                            "title": ep.get('title'),
                            "date": ep.get('air_date'),
                            "url": ep.get('url'),
                            "thumbnail": ep.get('thumbnail'),
                            "lastmod": ep.get('lastmod'),
                            "video_files": ep.get('video_files', [])
                        })
                        
                    # Add season data
                    final_seasons.append({
                        "season_number": season_num,
                        "title": f"Season {season_num}",
                        "episode_count": len(final_episodes),
                        "episodes": final_episodes
                    })
                
                # If no seasons were created but we have original seasons data, try to use it
                if not final_seasons and show.get('seasons'):
                    try:
                        # If this is a string, parse it as JSON
                        if isinstance(show['seasons'], str):
                            seasons_data = json.loads(show['seasons'])
                            final_seasons = seasons_data
                            LOGGER.debug(f"Using original seasons JSON data for {show.get('title_en')}")
                    except (json.JSONDecodeError, TypeError) as e:
                        LOGGER.warning(f"Failed to parse original seasons data for {show.get('title_en')}: {e}")
                
                # Assign processed data to the show
                show['seasons'] = final_seasons
                show['full_episodes'] = related_eps

            # Save all data to the output file
            data['shows'] = shows
            data['episodes'] = all_episodes

            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2 if pretty else None, ensure_ascii=False)

            LOGGER.info(f"Exported database to JSON: {output_path}")
            return True
        except Exception as e:
            LOGGER.error(f"Error exporting to JSON: {e}")
            return False

    def _load_table_with_json_fields(self, table: str, json_fields: List[str]) -> List[Dict]:
        """
        Load table data and parse JSON fields.
        
        Args:
            table: Table name
            json_fields: List of fields containing JSON data
            
        Returns:
            List of row dictionaries with parsed JSON fields
        """
        try:
            # Get all rows from the table
            rows = self.fetchall(f"SELECT * FROM {table}")
            
            # Process each row
            result = []
            for row in rows:
                # Convert sqlite3.Row to dict
                row_dict = dict(row)
                
                # Parse JSON fields
                for field in json_fields:
                    if field in row_dict and row_dict[field]:
                        try:
                            if isinstance(row_dict[field], str):
                                row_dict[field] = json.loads(row_dict[field])
                        except json.JSONDecodeError:
                            LOGGER.warning(f"Failed to parse JSON in {field} for {table} {row_dict.get('url', row_dict.get('id'))}")
                            row_dict[field] = []
                            
                result.append(row_dict)
                
            return result
        except sqlite3.Error as e:
            LOGGER.error(f"Error loading table {table}: {e}")
            return []