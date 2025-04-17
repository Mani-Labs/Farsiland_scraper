# Farsiland Scraper

A Python-based web scraper for extracting, organizing, and archiving content from Farsiland.com.

![Python](https://img.shields.io/badge/python-3.8%2B-blue)
![Scrapy](https://img.shields.io/badge/scrapy-2.11%2B-green)
![License](https://img.shields.io/badge/license-MIT-orange)

## Overview

Farsiland Scraper is a comprehensive solution for systematically extracting and organizing content from Farsiland.com. The project uses Scrapy along with custom modules to create a robust and maintainable scraper that can be run locally or deployed via Docker.

Key features:
- Extraction of movies, TV shows, and episode metadata
- Sitemap-based URL discovery for efficient scraping
- Caching system to reduce bandwidth usage and server load
- SQLite database for structured data storage
- Notification system for new content
- Docker support for easy deployment

## Installation

### Prerequisites
- Python 3.8 or higher
- pip (Python package installer)
- Docker (optional, for containerized deployment)

### Local Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/yourusername/farsiland-scraper.git
   cd farsiland-scraper
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

### Docker Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/yourusername/farsiland-scraper.git
   cd farsiland-scraper
   ```

2. Build and run the Docker container:
   ```bash
   docker-compose up -d
   ```

## Project Structure

```
/farsiland-scraper
├── farsiland_scraper/
│   ├── __init__.py
│   ├── config.py                   # Configuration settings
│   ├── run.py                      # Main entry point
│   ├── fetch.py                    # URL fetching and caching
│   ├── items.py                    # Scrapy item definitions
│   ├── settings.py                 # Scrapy settings
│   ├── test_kit.py                 # Testing framework
│   ├── database/
│   │   ├── __init__.py
│   │   └── models.py               # Database models and operations
│   ├── pipelines/
│   │   ├── __init__.py
│   │   ├── json_serialization.py   # Item serialization pipeline
│   │   └── save_to_db.py           # Database storage pipeline
│   ├── resolvers/
│   │   ├── __init__.py
│   │   └── video_link_resolver.py  # Video URL extraction
│   ├── spiders/
│   │   ├── __init__.py
│   │   ├── episodes_spider.py      # Spider for TV episodes
│   │   ├── movies_spider.py        # Spider for movies
│   │   └── series_spider.py        # Spider for TV series
│   └── utils/
│       ├── __init__.py
│       ├── new_item_tracker.py     # Tracks and notifies about new content
│       └── sitemap_parser.py       # Parses sitemap for URL discovery
├── data/                           # Extracted data storage
├── logs/                           # Log files
├── cache/                          # Cache storage
├── scrapy.cfg                      # Scrapy configuration
├── docker-compose.yml              # Docker Compose configuration
├── Dockerfile                      # Docker build instructions
└── requirements.txt                # Python dependencies
```

## Usage

### Basic Usage

Run the scraper with default settings:
```bash
python -m farsiland_scraper.run
```

### Command Line Options

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

### Common Use Cases

1. **Update sitemap and scrape all content types**:
   ```bash
   python -m farsiland_scraper.run --update-sitemap --sitemap --spiders all --export --notify
   ```

2. **Scrape only TV series with higher concurrency**:
   ```bash
   python -m farsiland_scraper.run --sitemap --spiders series --concurrent-requests 16
   ```

3. **Run continuously as a daemon with notifications**:
   ```bash
   python -m farsiland_scraper.run --daemon --sitemap --notify
   ```

4. **Scrape a single URL**:
   ```bash
   python -m farsiland_scraper.run --url https://farsiland.com/tvshows/example-show/
   ```

### Docker Usage

When using Docker, the scraper runs in daemon mode by default. You can customize the behavior by modifying the `docker-compose.yml` file:

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

## Configuration

The scraper's behavior can be configured through environment variables or by modifying `config.py`:

| Environment Variable      | Description                                    | Default Value        |
|---------------------------|------------------------------------------------|----------------------|
| FARSILAND_DATA_DIR        | Directory to store extracted data              | ./data               |
| FARSILAND_LOG_DIR         | Directory to store log files                   | ./logs               |
| FARSILAND_CACHE_DIR       | Directory to store cached content              | ./cache              |
| FARSILAND_DB_PATH         | Path to SQLite database                        | ./data/farsiland.db  |
| FARSILAND_JSON_PATH       | Path to exported JSON file                     | ./data/site_index.json |
| FARSILAND_BASE_URL        | Base URL of the target website                 | https://farsiland.com |
| FARSILAND_MAX_ITEMS       | Maximum items to scrape per category           | 10                   |
| FARSILAND_SCRAPE_INTERVAL | Interval between scrapes in daemon mode (secs) | 600                  |
| FARSILAND_REQUEST_TIMEOUT | HTTP request timeout in seconds                | 30                   |
| FARSILAND_RETRY_COUNT     | Number of retry attempts for failed requests   | 3                    |
| FARSILAND_LOG_LEVEL       | Logging level (debug, info, warning, error)    | info                 |

## Testing

The project includes a comprehensive testing framework. Run the tests with:

```bash
python -m farsiland_scraper.test_kit
```

For specific tests:
```bash
python -m farsiland_scraper.test_kit --test fetch
python -m farsiland_scraper.test_kit --test database
python -m farsiland_scraper.test_kit --test sitemap
python -m farsiland_scraper.test_kit --test series_spider
python -m farsiland_scraper.test_kit --test episodes_spider
python -m farsiland_scraper.test_kit --test integration
```

Enable debugging output:
```bash
python -m farsiland_scraper.test_kit --debug
```

Clean test directories:
```bash
python -m farsiland_scraper.test_kit --clean
```

## Data Structure

The scraper organizes data into three main tables:

1. **shows**: TV series information including title, poster, description, and season/episode structure
2. **episodes**: Individual episode metadata including video links, air dates, and parent show references
3. **movies**: Movie information including title, poster, description, and video links

Exported JSON data maintains these relationships and includes additional metadata.

## Contributing

Contributions are welcome! To contribute:

1. Fork the repository
2. Create a feature branch: `git checkout -b feature-name`
3. Commit your changes: `git commit -m 'Add some feature'`
4. Push to the branch: `git push origin feature-name`
5. Submit a pull request

Please ensure your code follows project conventions and includes appropriate tests.

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgements

- [Scrapy](https://scrapy.org/) - The web crawling framework
- [BeautifulSoup](https://www.crummy.com/software/BeautifulSoup/) - HTML parsing library
- [aiohttp](https://docs.aiohttp.org/) - Asynchronous HTTP client/server
- [Docker](https://www.docker.com/) - Containerization platform