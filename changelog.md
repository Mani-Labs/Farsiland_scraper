# Changelog

All notable changes to the Farsiland Scraper project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [2.0.0] - 2025-05-01

Complete system refactoring with significant architectural improvements and enhanced functionality.

### Added
- Comprehensive test framework (`test_kit.py`)
- Environment variable support for all configuration options
- Atomic file operations for improved data integrity
- File locking mechanism for cache access
- Exponential backoff with jitter for network retries
- Detailed docstrings across all modules
- Proper error context in log messages
- Docker healthcheck mechanism

### Changed
- Rewrote `series_spider.py` with modular extraction methods
- Rewrote `episodes_spider.py` with improved architecture
- Converted `sitemap_parser.py` to class-based design
- Simplified extraction logic across all spiders
- Enhanced URL detection through centralized patterns
- Improved selectors with multiple fallbacks
- Reorganized config module with logical grouping
- Standardized logging format across all modules
- Updated the default MAX_ITEMS_PER_CATEGORY from 3 to 10

### Fixed
- SQL injection vulnerabilities in database operations
- File handle leaks in fetch module
- Missing `mark_content_as_processed()` method
- Inefficient JSON field handling
- Complex nested conditionals in run.py
- Inconsistent error handling
- Duplicated code across spiders
- Inappropriate log levels for debug messages

### Security
- Added parameterized queries for all database operations
- Implemented proper input validation throughout the codebase
- Used secure file operations for all data writing

## [1.1.0] - 2025-04-15

### Added
- Docker support with docker-compose.yml
- Daemon mode for continuous operation
- Simple notification system for new content

### Changed
- Improved error handling in fetch module
- Enhanced sitemap parsing reliability
- Added more detailed logging

### Fixed
- Several parsing issues for edge cases
- Occasional duplicate entries in database

## [1.0.0] - 2025-04-01

Initial release of Farsiland Scraper.

### Features
- Basic scraping of movies, TV shows, and episodes
- SQLite database storage
- JSON export functionality
- Simple caching system