# File: farsiland_scraper/items.py
# Version: 2.3.0
# Last Updated: 2025-05-01 15:30

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
    
    # Episode URL tracking (for cross-reference)
    episode_urls = scrapy.Field()  # List of episode URLs discovered in this show
    
    # Flags and timestamps
    is_new = scrapy.Field(serializer=bool)  # Whether this is a new or updated item
    last_scraped = scrapy.Field(serializer=str)  # Timestamp when the item was last scraped
    cached_at = scrapy.Field(serializer=str)  # Timestamp when the item was cached
    source = scrapy.Field(serializer=str)  # Source of the data


class MovieItem(scrapy.Item):
    """
    Item representing a movie.
    
    A movie contains metadata about a standalone film.
    """
    # Identifiers
    url = scrapy.Field(serializer=str)  # Primary key, unique URL of the movie
    sitemap_url = scrapy.Field(serializer=str)  # URL in sitemap (can be different from url)
    lastmod = scrapy.Field(serializer=str)  # Last modification timestamp from sitemap
    
    # Basic metadata
    title_en = scrapy.Field(serializer=str)  # English title
    title_fa = scrapy.Field(serializer=str)  # Farsi title
    poster = scrapy.Field(serializer=str)  # URL to poster image
    description = scrapy.Field(serializer=str)  # Movie description/synopsis
    release_date = scrapy.Field(serializer=str)  # Release date
    year = scrapy.Field(serializer=int)  # Release year
    
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
    
    # Video files
    video_files = scrapy.Field()  # List of video files (VideoFileItem objects)
    
    # Flags and timestamps
    is_new = scrapy.Field(serializer=int)  # Whether this is a new or updated item (using int for DB compatibility)
    last_scraped = scrapy.Field(serializer=str)  # Timestamp when the item was last scraped
    cached_at = scrapy.Field(serializer=str)  # Timestamp when the item was cached
    source = scrapy.Field(serializer=str)  # Source of the data


class EpisodeItem(scrapy.Item):
    """
    Item representing a TV show episode.
    
    An episode belongs to a TV show and contains metadata and video links.
    """
    # Identifiers
    url = scrapy.Field(serializer=str)  # Primary key, unique URL of the episode
    sitemap_url = scrapy.Field(serializer=str)  # URL in sitemap
    lastmod = scrapy.Field(serializer=str)  # Last modification timestamp from sitemap
    
    # Relationship
    show_url = scrapy.Field(serializer=str)  # URL of the parent show
    
    # Episode metadata
    season_number = scrapy.Field(serializer=int)  # Season number
    episode_number = scrapy.Field(serializer=int)  # Episode number within the season
    title = scrapy.Field(serializer=str)  # Episode title
    air_date = scrapy.Field(serializer=str)  # Air date
    thumbnail = scrapy.Field(serializer=str)  # Thumbnail image URL
    
    # Video files
    video_files = scrapy.Field()  # List of video files (VideoFileItem objects)
    
    # Flags and timestamps
    is_new = scrapy.Field(serializer=bool)  # Whether this is a new or updated item
    last_scraped = scrapy.Field(serializer=str)  # Timestamp when the item was last scraped
    cached_at = scrapy.Field(serializer=str)  # Timestamp when the item was cached
    source = scrapy.Field(serializer=str)  # Source of the data


class VideoFileItem(scrapy.Item):
    """
    Item representing a video file.
    
    A video file contains information about a playable media file, including
    its quality, URL, and other metadata.
    """
    # Metadata
    quality = scrapy.Field(serializer=str)  # Quality label (e.g., "720", "1080")
    size = scrapy.Field(serializer=str)  # File size (e.g., "1.2 GB")
    
    # URLs
    url = scrapy.Field(serializer=str)  # Primary download URL
    mirror_url = scrapy.Field(serializer=str)  # Mirror/alternate download URL