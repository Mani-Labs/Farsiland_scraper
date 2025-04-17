# File: farsiland_scraper/items.py
# Version: 2.0.0
# Last Updated: 2025-04-19 15:00
#
# Changelog:
# - Added detailed docstrings for all item classes and fields
# - Ensured consistent field types with appropriate comments
# - Clarified relationships between item types
# - Added TypeHints for serializer functions

import scrapy
from typing import Dict, List, Union, Optional, Any, cast

class ShowItem(scrapy.Item):
    """
    Item representing a TV show/series.
    
    A show contains general metadata and can have multiple seasons and episodes.
    Related items:
    - SeasonItem: Represents a season of this show (many-to-one)
    - EpisodeItem: Represents episodes in this show (many-to-one)
    """
    # Identifiers
    url = scrapy.Field(serializer=str)  # Primary key, unique URL of the show
    sitemap_url = scrapy.Field(serializer=str)  # URL in sitemap (can be different from url)
    lastmod = scrapy.Field(serializer=str)  # Last modification timestamp from sitemap
    
    # Basic metadata
    title_en = scrapy.Field(serializer=str)  # English title
    title_fa = scrapy.Field(serializer=str)  # Farsi title
    poster = scrapy.Field(serializer=str)  # URL to poster image
    description = scrapy.Field(serializer=str)  # Show description/synopsis
    first_air_date = scrapy.Field(serializer=str)  # Date of first episode airing
    
    # Ratings
    rating = scrapy.Field(serializer=float)  # Average rating (0-10)
    rating_count = scrapy.Field(serializer=int)  # Number of ratings
    
    # Structure
    season_count = scrapy.Field(serializer=int)  # Number of seasons
    episode_count = scrapy.Field(serializer=int)  # Total number of episodes
    
    # Categories and people
    genres = scrapy.Field()  # List of genre strings
    directors = scrapy.Field()  # List of director names
    cast = scrapy.Field()  # List of cast member names
    
    # Engagement metrics
    social_shares = scrapy.Field(serializer=int)  # Number of social media shares
    comments_count = scrapy.Field(serializer=int)  # Number of comments
    
    # Season data
    seasons = scrapy.Field()  # List of season data (can contain SeasonItem objects)
    
    # Flags
    is_new = scrapy.Field(serializer=bool)  # Whether this is a new or updated item

class SeasonItem(scrapy.Item):
    """
    Item representing a season of a TV show.
    
    A season belongs to a show and contains multiple episodes.
    Relationships:
    - Parent: ShowItem (one-to-many)
    - Children: EpisodeItem (one-to-many)
    """
    show_url = scrapy.Field(serializer=str)  # Foreign key to ShowItem.url
    season_number = scrapy.Field(serializer=int)  # Season number (1, 2, 3, etc.)
    episodes = scrapy.Field()  # List of episode data (can contain EpisodeItem objects)

class EpisodeItem(scrapy.Item):
    """
    Item representing a TV show episode.
    
    An episode belongs to a show and a specific season.
    Relationships:
    - Parent: ShowItem (many-to-one)
    - Parent: SeasonItem (many-to-one)
    """
    # Identifiers
    url = scrapy.Field(serializer=str)  # Primary key, unique URL of the episode
    sitemap_url = scrapy.Field(serializer=str)  # URL in sitemap
    lastmod = scrapy.Field(serializer=str)  # Last modification timestamp from sitemap
    
    # Relationships
    show_url = scrapy.Field(serializer=str)  # Foreign key to ShowItem.url
    season_number = scrapy.Field(serializer=int)  # Season number
    episode_number = scrapy.Field(serializer=int)  # Episode number within the season
    
    # Metadata
    title = scrapy.Field(serializer=str)  # Episode title
    air_date = scrapy.Field(serializer=str)  # Original air date
    thumbnail = scrapy.Field(serializer=str)  # URL to episode thumbnail
    
    # Content
    video_files = scrapy.Field()  # List of VideoFileItem objects
    
    # Flags
    is_new = scrapy.Field(serializer=bool)  # Whether this is a new or updated item

class MovieItem(scrapy.Item):
    """
    Item representing a movie.
    
    A movie is a standalone item with no parent-child relationships.
    Related items:
    - VideoFileItem: Contains video file information (embedded)
    """
    # Identifiers
    url = scrapy.Field(serializer=str)  # Primary key, unique URL of the movie
    sitemap_url = scrapy.Field(serializer=str)  # URL in sitemap
    lastmod = scrapy.Field(serializer=str)  # Last modification timestamp from sitemap
    
    # Basic metadata
    title_en = scrapy.Field(serializer=str)  # English title
    title_fa = scrapy.Field(serializer=str)  # Farsi title
    poster = scrapy.Field(serializer=str)  # URL to poster image
    description = scrapy.Field(serializer=str)  # Movie description/synopsis
    release_date = scrapy.Field(serializer=str)  # Release date string
    year = scrapy.Field(serializer=int)  # Release year as integer
    
    # Ratings
    rating = scrapy.Field(serializer=float)  # Average rating (0-10)
    rating_count = scrapy.Field(serializer=int)  # Number of ratings
    
    # Categories and people
    genres = scrapy.Field()  # List of genre strings
    directors = scrapy.Field()  # List of director names
    cast = scrapy.Field()  # List of cast member names
    
    # Engagement metrics
    social_shares = scrapy.Field(serializer=int)  # Number of social media shares
    comments_count = scrapy.Field(serializer=int)  # Number of comments
    
    # Content
    video_files = scrapy.Field()  # List of VideoFileItem objects
    
    # Flags
    is_new = scrapy.Field(serializer=bool)  # Whether this is a new or updated item

class VideoFileItem(scrapy.Item):
    """
    Item representing a video file.
    
    Video files are associated with movies or episodes.
    This is typically embedded within MovieItem or EpisodeItem.
    """
    quality = scrapy.Field(serializer=str)  # Video quality (e.g., "720p", "1080p")
    url = scrapy.Field(serializer=str)  # Primary URL to the video file
    mirror_url = scrapy.Field(serializer=str)  # Alternative URL (backup)
    size = scrapy.Field(serializer=str)  # File size (e.g., "1.2 GB")