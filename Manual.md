# Farsiland Scraper: User Manual

This manual provides detailed instructions for installing, configuring, and operating the Farsiland Scraper system.

## Table of Contents

1. [Introduction](#introduction)
2. [Installation](#installation)
3. [Configuration](#configuration)
4. [Operation Modes](#operation-modes)
5. [Data Management](#data-management)
6. [Troubleshooting](#troubleshooting)
7. [Advanced Usage](#advanced-usage)
8. [Docker Deployment](#docker-deployment)
9. [Appendix](#appendix)

## Introduction

Farsiland Scraper is a specialized web scraping system designed to extract, index, and archive content from Farsiland.com. It focuses on three main content types:

- **TV Series**: Complete shows with seasons and episodes
- **Episodes**: Individual TV show episodes with video links
- **Movies**: Feature films with metadata and video links

The scraper is built on a modular architecture that allows for incremental updates, efficient caching, and structured data storage.

## Installation

### System Requirements

- Python 3.8 or higher
- 512MB RAM minimum (1GB+ recommended)
- 1GB free disk space minimum
- Internet connection

### Local Installation

1. **Clone the repository**:
   ```bash
   git clone https://github.com/yourusername/farsiland-scraper.git
   cd farsiland-scraper
   ```

2. **Create a virtual environment** (recommended):
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Create required directories**:
   ```bash
   mkdir -p data logs cache
   ```

5. **Verify installation**:
   ```bash
   python -m farsiland_scraper.run --help
   ```

## Configuration

### Environment Variables

The scraper can be configured through environment variables:

| Variable                 | Description                          | Default                    |
|--------------------------|--------------------------------------|----------------------------|
| FARSILAND_DATA_DIR       | Data storage path                    | ./data                     |
| FARSILAND_LOG_DIR        | Log files path                       | ./logs                     |
| FARSILAND_CACHE_DIR      | HTML cache path                      | ./cache                    |
| FARSILAND_DB_PATH        | SQLite database path                 | ./data/farsiland.db        |
| FARSILAND_JSON_PATH      | JSON export path                     | ./data/site_index.json     |
| FARSILAND_BASE_URL       | Target website URL                   | https://farsiland.com      |
| FARSILAND_SITEMAP_URL    | Sitemap URL                          | (BASE_URL)/sitemap_index.xml |
| FARSILAND_MAX_ITEMS      | Items per category limit             | 10                         |
| FARSILAND_LOG_LEVEL      | Log level                            | info                       |
| FARSILAND_REQUEST_TIMEOUT | HTTP request timeout (seconds)      | 30                         |
| FARSILAND_RETRY_COUNT    | Failed request retry attempts        | 3                          |
| FARSILAND_RETRY_DELAY    | Delay between retries (seconds)      | 5                          |
| FARSILAND_SCRAPE_INTERVAL | Daemon mode interval (seconds)      | 600                        |

### Configuration File

You can also modify settings directly in `farsiland_scraper/config.py`, but environment variables take precedence.

## Operation Modes

The scraper can operate in several different modes depending on your needs:

### One-Time Scrape

Run a single scrape operation and exit:

```bash
python -m farsiland_scraper.run --sitemap --spiders all
```

### Daemon Mode

Run continuously, periodically checking for new content:

```bash
python -m farsiland_scraper.run --daemon --sitemap --notify
```

### Targeted Scrape

Scrape a specific URL or content type:

```bash
# Scrape a single URL
python -m farsiland_scraper.run --url https://farsiland.com/tvshows/example-show/

# Scrape only TV series
python -m farsiland_scraper.run --sitemap --spiders series
```

### Update Sitemap Only

Only update the sitemap without scraping content:

```bash
python -m farsiland_scraper.run --update-sitemap
```

## Data Management

### Database Structure

The scraper uses an SQLite database with three main tables:

1. **shows**: TV series metadata
   - Primary key: `url`
   - Contains: title, description, poster, genres, cast, seasons data

2. **episodes**: Individual episodes
   - Primary key: `url`
   - Foreign key: `show_url` references shows.url
   - Contains: title, air date, video links

3. **movies**: Movies metadata
   - Primary key: `url`
   - Contains: title, description, poster, genres, cast, video links

### Exporting Data

Export the database to JSON:

```bash
python -m farsiland_scraper.run --export --export-file output.json
```

The JSON structure preserves relationships between shows and episodes.

### Cache Management

The scraper caches HTML content to reduce bandwidth usage and server load. To manage the cache:

- **Force refresh** (ignore cache):
  ```bash
  python -m farsiland_scraper.run --force-refresh
  ```

- **Clear cache** (remove all cached files):
  ```bash
  rm -rf cache/pages/*
  ```

## Troubleshooting

### Common Issues

1. **Connection errors**:
   - Check your internet connection
   - Verify the target website is accessible
   - Try increasing the timeout: `export FARSILAND_REQUEST_TIMEOUT=60`

2. **Rate limiting/blocking**:
   - Decrease concurrency: `--concurrent-requests 4`
   - Increase delay between requests: `--download-delay 2`

3. **Parse errors**:
   - Site structure may have changed; check logs for details
   - Update selectors in the corresponding spider file

### Logs

Logs are stored in the `logs` directory by default. To enable verbose logging:

```bash
python -m farsiland_scraper.run --verbose
```

To specify a custom log file:

```bash
python -m farsiland_scraper.run --log-file custom_log.log
```

### Testing

Run tests to verify system functionality:

```bash
python -m farsiland_scraper.test_kit
```

## Advanced Usage

### Custom Spider Selection

Run multiple specific spiders:

```bash
python -m farsiland_scraper.run --spiders series episodes
```

### Concurrent Request Tuning

Adjust concurrency for performance:

```bash
python -m farsiland_scraper.run --concurrent-requests 16 --download-delay 0.2
```

### Content Limits

Limit the amount of content scraped:

```bash
python -m farsiland_scraper.run --limit 50
```

### New Content Notification

Enable notifications for new content:

```bash
python -m farsiland_scraper.run --notify
```

This creates a JSON notification file with details of newly discovered content.

## Docker Deployment

### Basic Docker Usage

1. **Build and start the container**:
   ```bash
   docker-compose up -d
   ```

2. **View logs**:
   ```bash
   docker logs -f farsiland-scraper
   ```

3. **Stop the container**:
   ```bash
   docker-compose down
   ```

### Docker Configuration

Modify `docker-compose.yml` to customize the deployment:

```yaml
version: '3.8'

services:
  farsiland-scraper:
    build: .
    container_name: farsiland-scraper
    restart: unless-stopped
    volumes:
      - ./data:/app/data
      - ./logs:/app/logs
    environment:
      - TZ=UTC
      - FARSILAND_MAX_ITEMS=20
      - FARSILAND_LOG_LEVEL=info
    command: python -m farsiland_scraper.run --daemon --notify --sitemap
```

### Unraid Configuration

For Unraid users:
1. Add a new Docker container
2. Use the template URL or custom configuration
3. Map the following paths:
   - `/app/data` -> `/path/on/host/data`
   - `/app/logs` -> `/path/on/host/logs`
4. Set environment variables as needed

## Appendix

### Command Line Reference

```
usage: run.py [-h] [--daemon] [--spiders {series,episodes,movies,all} [{series,episodes,movies,all} ...]]
              [--url URL] [--force-refresh] [--sitemap] [--update-sitemap]
              [--sitemap-file SITEMAP_FILE] [--limit LIMIT]
              [--concurrent-requests CONCURRENT_REQUESTS] [--download-delay DOWNLOAD_DELAY]
              [--export] [--export-file EXPORT_FILE] [--notify] [--verbose]
              [--log-file LOG_FILE]

Farsiland Scraper

options:
  -h, --help            show this help message and exit
  --daemon              Run the scraper continuously (default: False)
  --spiders {series,episodes,movies,all} [{series,episodes,movies,all} ...]
                        Spiders to run (default: ['all'])
  --url URL             Scrape a specific URL (default: None)
  --force-refresh       Ignore cache and re-fetch all HTML (default: False)
  --sitemap             Use parsed sitemap URLs instead of crawling site (default: False)
  --update-sitemap      Update sitemap data before scraping (default: False)
  --sitemap-file SITEMAP_FILE
                        Path to sitemap file (default: None)
  --limit LIMIT         Limit number of items to crawl per spider (default: 10)
  --concurrent-requests CONCURRENT_REQUESTS
                        Maximum concurrent requests (default: None)
  --download-delay DOWNLOAD_DELAY
                        Delay between requests in seconds (default: None)
  --export              Export database to JSON after scraping (default: False)
  --export-file EXPORT_FILE
                        Path to export JSON file (default: None)
  --notify              Notify about new content after scraping (default: False)
  --verbose             Enable verbose logging (default: False)
  --log-file LOG_FILE   Path to log file (default: None)
```

### Test Kit Reference

```
usage: test_kit.py [-h] [--test TESTS] [--debug] [--clean]

Test kit for Farsiland Scraper

options:
  -h, --help     show this help message and exit
  --test TESTS   Specific test to run (can be specified multiple times)
  --debug        Enable debug logging
  --clean        Clean test output directory and exit
```

### File Structure Reference

```
/farsiland-scraper
├── farsiland_scraper/        # Main package
│   ├── database/             # Database models and operations
│   ├── pipelines/            # Scrapy pipelines
│   ├── resolvers/            # Content resolvers
│   ├── spiders/              # Scrapy spiders
│   └── utils/                # Utility modules
├── data/                     # Data storage
├── logs/                     # Log files
└── cache/                    # Cache storage
```

### Best Practices

1. **Courteous scraping**:
   - Use reasonable delays between requests
   - Limit concurrent connections
   - Cache content to reduce bandwidth usage

2. **Regular maintenance**:
   - Monitor logs for parsing errors
   - Update selectors if site structure changes
   - Periodically clean unnecessary cache files

3. **Data management**:
   - Regularly back up your database
   - Export to JSON for readable backups
   - Consider archiving older content