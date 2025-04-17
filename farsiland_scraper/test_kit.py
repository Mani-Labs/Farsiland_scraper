#!/usr/bin/env python3
# File: farsiland_scraper/test_kit.py
# Version: 1.0.0
# Last Updated: 2025-05-01 14:30
#
# Description: Comprehensive testing script for the Farsiland Scraper project
#
# Usage Instructions:
# ------------------
# 1. Create test directories:
#    mkdir -p test_output/data test_output/logs test_output/cache test_output/db
#
# 2. Run the entire test suite:
#    python -m farsiland_scraper.test_kit
#
# 3. Run a specific test:
#    python -m farsiland_scraper.test_kit --test fetch
#    python -m farsiland_scraper.test_kit --test database
#    python -m farsiland_scraper.test_kit --test sitemap
#    python -m farsiland_scraper.test_kit --test series_spider
#    python -m farsiland_scraper.test_kit --test episodes_spider
#    python -m farsiland_scraper.test_kit --test integration
#
# 4. Run tests with debugging output:
#    python -m farsiland_scraper.test_kit --debug
#
# 5. Clean test output directory:
#    python -m farsiland_scraper.test_kit --clean

import os
import sys
import json
import time
import shutil
import logging
import argparse
import tempfile
import traceback
from pathlib import Path
from datetime import datetime
from unittest.mock import patch, MagicMock

# Set up test environment
TEST_DIR = Path("./test_output")
TEST_DATA_DIR = TEST_DIR / "data"
TEST_LOG_DIR = TEST_DIR / "logs"
TEST_CACHE_DIR = TEST_DIR / "cache"
TEST_DB_DIR = TEST_DIR / "db"

# Configure test environment variables
os.environ['FARSILAND_DATA_DIR'] = str(TEST_DATA_DIR)
os.environ['FARSILAND_LOG_DIR'] = str(TEST_LOG_DIR)
os.environ['FARSILAND_CACHE_DIR'] = str(TEST_CACHE_DIR)
os.environ['FARSILAND_DB_PATH'] = str(TEST_DB_DIR / "test.db")
os.environ['FARSILAND_MAX_ITEMS'] = "2"  # Limit items during testing
os.environ['FARSILAND_LOG_LEVEL'] = "debug"

# Ensure test directories exist
for dir_path in [TEST_DIR, TEST_DATA_DIR, TEST_LOG_DIR, TEST_CACHE_DIR, TEST_DB_DIR]:
    dir_path.mkdir(exist_ok=True, parents=True)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    handlers=[
        logging.FileHandler(TEST_LOG_DIR / "test_kit.log"),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("test_kit")

# Sample HTML content for testing
SAMPLE_SERIES_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Sample Series</title>
    <meta property="og:title" content="Oscar Series">
    <meta property="og:description" content="A sample TV show for testing">
    <meta property="og:image" content="https://farsiland.com/wp-content/uploads/2023/05/oscar-poster.jpg">
</head>
<body>
    <h1>Oscar Series</h1>
    <div class="poster">
        <img src="https://farsiland.com/wp-content/uploads/2023/05/oscar-poster.jpg" alt="Poster">
    </div>
    <div class="description">
        <p>A sample TV show for testing purposes.</p>
    </div>
    <div class="extra">
        <span class="date">2023-05-01</span>
    </div>
    <div class="sgeneros">
        <a href="#">Comedy</a>
        <a href="#">Drama</a>
    </div>
    <div class="seasons">
        <div class="se-c">
            <div class="se-q">
                <div class="se-t">Season 1</div>
            </div>
            <div class="se-a">
                <ul class="episodios">
                    <li>
                        <div class="imagen"><img src="https://farsiland.com/wp-content/uploads/2023/05/s01e01.jpg"></div>
                        <div class="numerando">1 - 1</div>
                        <div class="episodiotitle">
                            <a href="https://farsiland.com/episodes/oscar-se01-ep01/">Pilot</a>
                            <span class="date">2023-05-01</span>
                        </div>
                    </li>
                    <li>
                        <div class="imagen"><img src="https://farsiland.com/wp-content/uploads/2023/05/s01e02.jpg"></div>
                        <div class="numerando">1 - 2</div>
                        <div class="episodiotitle">
                            <a href="https://farsiland.com/episodes/oscar-se01-ep02/">Second Episode</a>
                            <span class="date">2023-05-08</span>
                        </div>
                    </li>
                </ul>
            </div>
        </div>
    </div>
</body>
</html>"""

SAMPLE_EPISODE_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Oscar S01E01</title>
    <meta property="og:title" content="Oscar S01E01: Pilot">
    <meta property="og:image" content="https://farsiland.com/wp-content/uploads/2023/05/s01e01.jpg">
</head>
<body>
    <h1 class="player-title">Oscar S01E01: Pilot</h1>
    <div class="breadcrumb">
        <li><a href="https://farsiland.com/">Home</a></li>
        <li><a href="https://farsiland.com/tvshows/oscar/">Oscar</a></li>
        <li>Season 1</li>
        <li>Episode 1</li>
    </div>
    <div class="thumb">
        <img src="https://farsiland.com/wp-content/uploads/2023/05/s01e01.jpg" alt="Episode Thumbnail">
    </div>
    <div class="extra">
        <span class="date">2023-05-01</span>
    </div>
    <div id="download">
        <table>
            <tr id="link-1">
                <td>
                    <form id="dlform1" action="https://farsiland.com/get/" method="post">
                        <input type="hidden" name="fileid" value="12345">
                    </form>
                </td>
                <td><strong class="quality">720</strong></td>
                <td>500 MB</td>
            </tr>
            <tr id="link-2">
                <td>
                    <form id="dlform2" action="https://farsiland.com/get/" method="post">
                        <input type="hidden" name="fileid" value="67890">
                    </form>
                </td>
                <td><strong class="quality">1080</strong></td>
                <td>1.2 GB</td>
            </tr>
        </table>
    </div>
    <a href="https://farsiland.com/direct/sample.mp4">Direct Link</a>
</body>
</html>"""

SAMPLE_SITEMAP_XML = """<?xml version="1.0" encoding="UTF-8"?>
<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
    <sitemap>
        <loc>https://farsiland.com/tvshows-sitemap.xml</loc>
        <lastmod>2025-04-15T10:15:30+00:00</lastmod>
    </sitemap>
    <sitemap>
        <loc>https://farsiland.com/episodes-sitemap.xml</loc>
        <lastmod>2025-04-15T10:30:20+00:00</lastmod>
    </sitemap>
    <sitemap>
        <loc>https://farsiland.com/movies-sitemap.xml</loc>
        <lastmod>2025-04-15T09:45:10+00:00</lastmod>
    </sitemap>
</sitemapindex>"""

SAMPLE_TVSHOWS_SITEMAP = """<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
    <url>
        <loc>https://farsiland.com/tvshows/oscar/</loc>
        <lastmod>2025-04-10T08:15:30+00:00</lastmod>
    </url>
    <url>
        <loc>https://farsiland.com/tvshows/sample-show/</loc>
        <lastmod>2025-04-08T14:20:45+00:00</lastmod>
    </url>
</urlset>"""

# Classes for generating mock responses
class MockResponse:
    def __init__(self, content, status_code=200, url=""):
        self.content = content.encode('utf-8') if isinstance(content, str) else content
        self.status_code = status_code
        self.url = url
        self.headers = {}
        
    async def text(self):
        return self.content.decode('utf-8')
        
    def raise_for_status(self):
        if self.status_code >= 400:
            raise Exception(f"HTTP Error: {self.status_code}")


class MockClientSession:
    def __init__(self, responses=None):
        self.responses = responses or {}
        self.closed = False
        
    async def __aenter__(self):
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        self.closed = True
        
    async def get(self, url, **kwargs):
        if url in self.responses:
            return self.responses[url]
        return MockResponse("", 404, url)
        
    async def post(self, url, **kwargs):
        if url in self.responses:
            return self.responses[url]
        # If it's a form post to get/ endpoint, return a redirect to an MP4
        if '/get/' in url:
            resp = MockResponse("", 302, url)
            resp.headers['Location'] = 'https://farsiland.com/path/to/video.mp4'
            return resp
        return MockResponse("", 404, url)


def create_sample_files():
    """Create sample files for testing."""
    # Create sample sitemap files
    with open(TEST_DATA_DIR / "sitemap_index.xml", "w") as f:
        f.write(SAMPLE_SITEMAP_XML)
    
    with open(TEST_DATA_DIR / "tvshows-sitemap.xml", "w") as f:
        f.write(SAMPLE_TVSHOWS_SITEMAP)
    
    # Create parsed_urls.json
    parsed_urls = {
        "shows": [
            {"url": "https://farsiland.com/tvshows/oscar/", "lastmod": "2025-04-10T08:15:30+00:00"}
        ],
        "episodes": [
            {"url": "https://farsiland.com/episodes/oscar-se01-ep01/", "lastmod": "2025-04-10T08:20:15+00:00"}
        ],
        "movies": []
    }
    
    with open(TEST_DATA_DIR / "parsed_urls.json", "w") as f:
        json.dump(parsed_urls, f, indent=2)
    
    # Create sample HTML files
    cache_series_dir = TEST_CACHE_DIR / "pages" / "shows"
    cache_series_dir.mkdir(exist_ok=True, parents=True)
    
    with open(cache_series_dir / "farsiland.com-tvshows-oscar.html", "w") as f:
        f.write(SAMPLE_SERIES_HTML)
    
    cache_episodes_dir = TEST_CACHE_DIR / "pages" / "episodes"
    cache_episodes_dir.mkdir(exist_ok=True, parents=True)
    
    with open(cache_episodes_dir / "farsiland.com-episodes-oscar-se01-ep01.html", "w") as f:
        f.write(SAMPLE_EPISODE_HTML)


class TestCase:
    """Base class for test cases."""
    
    def __init__(self, name):
        self.name = name
        self.passed = False
        self.error = None
        self.start_time = None
        self.end_time = None
        
    def setup(self):
        """Setup before running the test."""
        pass
        
    def teardown(self):
        """Cleanup after running the test."""
        pass
        
    def run(self):
        """Run the test."""
        logger.info(f"Running test: {self.name}")
        self.start_time = time.time()
        
        try:
            self.setup()
            self.test()
            self.passed = True
            logger.info(f"Test {self.name} PASSED")
        except Exception as e:
            self.error = str(e)
            logger.error(f"Test {self.name} FAILED: {e}")
            logger.error(traceback.format_exc())
        finally:
            try:
                self.teardown()
            except Exception as cleanup_error:
                logger.error(f"Error during test cleanup: {cleanup_error}")
            
            self.end_time = time.time()
            elapsed = self.end_time - self.start_time
            logger.info(f"Test {self.name} completed in {elapsed:.2f} seconds")
            
    def test(self):
        """Actual test logic, to be implemented by subclasses."""
        raise NotImplementedError("Subclasses must implement test()")


class FetchTest(TestCase):
    """Test the fetch module."""
    
    def test(self):
        """Test fetch_sync function."""
        from farsiland_scraper.fetch import fetch_sync
        
        # Test 1: Basic fetch from cache
        content = fetch_sync("https://farsiland.com/tvshows/oscar/", "shows")
        assert content, "Failed to fetch content from cache"
        assert "Oscar Series" in content, "Content doesn't match expected"
        
        # Test 2: Test with non-existent URL (should return None or empty)
        content = fetch_sync("https://farsiland.com/non-existent/", "shows", force_refresh=True)
        assert content is None, "Should return None for non-existent URL with force_refresh"


class DatabaseTest(TestCase):
    """Test database functionality."""
    
    def test(self):
        """Test database operations."""
        from farsiland_scraper.database.models import Database
        
        # Initialize test database
        db = Database(db_path=str(TEST_DB_DIR / "db_test.sqlite"))
        
        try:
            # Test basic operations
            db.execute("CREATE TABLE IF NOT EXISTS test_table (id INTEGER PRIMARY KEY, name TEXT)")
            db.execute("INSERT INTO test_table (name) VALUES (?)", ["test_value_1"])
            db.execute("INSERT INTO test_table (name) VALUES (?)", ["test_value_2"])
            db.commit()
            
            # Test fetchall
            rows = db.fetchall("SELECT * FROM test_table ORDER BY id")
            assert len(rows) == 2, f"Expected 2 rows, got {len(rows)}"
            assert rows[0]['name'] == "test_value_1", f"Expected 'test_value_1', got '{rows[0]['name']}'"
            
            # Test fetchone
            row = db.fetchone("SELECT * FROM test_table WHERE name=?", ["test_value_2"])
            assert row is not None, "Expected a row but got None"
            assert row['name'] == "test_value_2", f"Expected 'test_value_2', got '{row['name']}'"
            
            # Test mark_content_as_processed
            db.execute("CREATE TABLE IF NOT EXISTS shows (id INTEGER PRIMARY KEY, url TEXT, is_new INTEGER)")
            db.execute("INSERT INTO shows (url, is_new) VALUES (?, ?)", ["https://example.com/show1", 1])
            db.execute("INSERT INTO shows (url, is_new) VALUES (?, ?)", ["https://example.com/show2", 1])
            db.commit()
            
            success = db.mark_content_as_processed("shows", [1, 2])
            assert success, "mark_content_as_processed should return True"
            
            row = db.fetchone("SELECT is_new FROM shows WHERE id=?", [1])
            assert row['is_new'] == 0, f"Expected is_new=0, got {row['is_new']}"
            
        finally:
            db.close()


class SitemapTest(TestCase):
    """Test sitemap parsing functionality."""
    
    @patch('aiohttp.ClientSession')
    def test(self, mock_session):
        """Test SitemapParser."""
        from farsiland_scraper.utils.sitemap_parser import SitemapParser
        
        # Configure mock to return sample sitemap content
        mock_session.return_value = MockClientSession({
            "https://farsiland.com/sitemap_index.xml": MockResponse(SAMPLE_SITEMAP_XML),
            "https://farsiland.com/tvshows-sitemap.xml": MockResponse(SAMPLE_TVSHOWS_SITEMAP)
        })
        
        # Initialize parser with test output file
        parser = SitemapParser(
            sitemap_url="https://farsiland.com/sitemap_index.xml",
            output_file=str(TEST_DATA_DIR / "sitemap_test_output.json")
        )
        
        # Run the parser
        success = parser.run()
        assert success, "SitemapParser.run() should return True"
        
        # Verify output file was created
        assert (TEST_DATA_DIR / "sitemap_test_output.json").exists(), "Output file not created"
        
        # Load and verify results
        with open(TEST_DATA_DIR / "sitemap_test_output.json", "r") as f:
            results = json.load(f)
            
        assert "shows" in results, "Results should contain 'shows' key"
        assert len(results["shows"]) > 0, "Should have extracted at least one show URL"


class SeriesSpiderTest(TestCase):
    """Test SeriesSpider functionality."""
    
    def test(self):
        """Test SeriesSpider initialization and basic functionality."""
        from farsiland_scraper.spiders.series_spider import SeriesSpider
        
        # Test spider initialization
        spider = SeriesSpider(
            start_urls=["https://farsiland.com/tvshows/oscar/"],
            max_items=1
        )
        
        assert spider.max_items == 1, f"Expected max_items=1, got {spider.max_items}"
        assert len(spider.start_urls) == 1, f"Expected 1 start URL, got {len(spider.start_urls)}"
        
        # Test URL validation
        valid = spider._is_series_url("https://farsiland.com/tvshows/oscar/")
        assert valid, "Should validate correct series URL"
        
        invalid = spider._is_series_url("https://farsiland.com/movies/oscar/")
        assert not invalid, "Should reject incorrect series URL"
        
        # Mock item creation and parsing
        show = spider._create_show_item("https://farsiland.com/tvshows/oscar/", "2025-04-10T08:15:30+00:00")
        assert show['url'] == "https://farsiland.com/tvshows/oscar/", "URL not set correctly"
        assert show['is_new'] is True, "New item should have is_new=True"
        
        # Test with BeautifulSoup parsing
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(SAMPLE_SERIES_HTML, 'html.parser')
        
        # Test individual extraction methods
        spider._extract_title(show, soup)
        assert show.get('title_en') == "Oscar Series", f"Expected 'Oscar Series', got '{show.get('title_en')}'"
        
        spider._extract_poster(show, soup)
        assert "oscar-poster.jpg" in show.get('poster', ""), "Poster URL not extracted correctly"
        
        spider._extract_seasons_and_episodes(show, soup)
        assert len(show.get('seasons', [])) == 1, f"Expected 1 season, got {len(show.get('seasons', []))}"
        assert show.get('season_count') == 1, f"Expected season_count=1, got {show.get('season_count')}"
        assert show.get('episode_count') == 2, f"Expected episode_count=2, got {show.get('episode_count')}"
        
        # Verify episode extraction
        episodes = show.get('seasons', [])[0].get('episodes', [])
        assert len(episodes) == 2, f"Expected 2 episodes, got {len(episodes)}"
        assert episodes[0].get('title') == "Pilot", f"Expected 'Pilot', got '{episodes[0].get('title')}'"
        assert episodes[1].get('episode_number') == 2, f"Expected episode_number=2, got {episodes[1].get('episode_number')}"


class EpisodesSpiderTest(TestCase):
    """Test EpisodesSpider functionality."""
    
    def test(self):
        """Test EpisodesSpider initialization and basic functionality."""
        from farsiland_scraper.spiders.episodes_spider import EpisodesSpider
        
        # Test spider initialization
        spider = EpisodesSpider(
            start_urls=["https://farsiland.com/episodes/oscar-se01-ep01/"],
            max_items=1
        )
        
        assert spider.max_items == 1, f"Expected max_items=1, got {spider.max_items}"
        assert len(spider.start_urls) == 1, f"Expected 1 start URL, got {len(spider.start_urls)}"
        
        # Test URL validation
        valid = spider._is_episode_url("https://farsiland.com/episodes/oscar-se01-ep01/")
        assert valid, "Should validate correct episode URL"
        
        invalid = spider._is_episode_url("https://farsiland.com/tvshows/oscar/")
        assert not invalid, "Should reject incorrect episode URL"
        
        # Mock item creation and parsing
        episode = spider._create_episode_item("https://farsiland.com/episodes/oscar-se01-ep01/", 
                                             "2025-04-10T08:20:15+00:00")
        assert episode['url'] == "https://farsiland.com/episodes/oscar-se01-ep01/", "URL not set correctly"
        assert episode['is_new'] is True, "New item should have is_new=True"
        
        # Test with BeautifulSoup parsing
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(SAMPLE_EPISODE_HTML, 'html.parser')
        
        # Test individual extraction methods
        spider._extract_title(episode, soup)
        assert episode.get('title') == "Oscar S01E01: Pilot", f"Expected 'Oscar S01E01: Pilot', got '{episode.get('title')}'"
        
        spider._extract_episode_info(episode, soup, episode['url'])
        assert episode.get('season_number') == 1, f"Expected season_number=1, got {episode.get('season_number')}"
        assert episode.get('episode_number') == 1, f"Expected episode_number=1, got {episode.get('episode_number')}"
        
        spider._extract_show_info(episode, soup)
        assert episode.get('show_url') == "https://farsiland.com/tvshows/oscar", \
            f"Expected 'https://farsiland.com/tvshows/oscar', got '{episode.get('show_url')}'"
        
        spider._extract_media_info(episode, soup)
        assert "s01e01.jpg" in episode.get('thumbnail', ""), "Thumbnail URL not extracted correctly"


class IntegrationTest(TestCase):
    """Integration test for the entire scraper."""
    
    def test(self):
        """Test the end-to-end workflow."""
        # Import run module
        from farsiland_scraper.run import parse_args, ScrapeManager
        
        # Create test arguments
        args = parse_args()
        args.spiders = ["series"]
        args.limit = 1
        args.verbose = True
        args.export = True
        args.export_file = str(TEST_DATA_DIR / "export_test.json")
        args.sitemap = True
        args.sitemap_file = str(TEST_DATA_DIR / "parsed_urls.json")
        
        # Create scrape manager
        manager = ScrapeManager(args)
        
        # Run the scraper once
        success = manager.run_once()
        assert success, "ScrapeManager.run_once() should return True"
        
        # Verify export file was created
        assert (TEST_DATA_DIR / "export_test.json").exists(), "Export file not created"
        
        # Load and verify results
        with open(TEST_DATA_DIR / "export_test.json", "r") as f:
            results = json.load(f)
            
        assert "shows" in results, "Results should contain 'shows' key"
        assert len(results["shows"]) > 0, "Should have extracted at least one show"


class TestRunner:
    """Run test cases and report results."""
    
    def __init__(self):
        self.tests = {}
        self.results = {
            "total": 0,
            "passed": 0,
            "failed": 0,
            "errors": []
        }
        
    def add_test(self, test_case):
        """Add a test case."""
        self.tests[test_case.name] = test_case
        
    def run_tests(self, test_names=None, debug=False):
        """Run specified tests or all tests."""
        if debug:
            logging.getLogger().setLevel(logging.DEBUG)
        
        to_run = {}
        if test_names:
            for name in test_names:
                if name in self.tests:
                    to_run[name] = self.tests[name]
                else:
                    logger.warning(f"Test '{name}' not found")
        else:
            to_run = self.tests
            
        self.results["total"] = len(to_run)
        
        logger.info(f"Running {len(to_run)} tests...")
        
        start_time = time.time()
        
        for name, test in to_run.items():
            test.run()
            if test.passed:
                self.results["passed"] += 1
            else:
                self.results["failed"] += 1
                self.results["errors"].append({
                    "name": name,
                    "error": test.error
                })
        
        end_time = time.time()
        self.results["duration"] = end_time - start_time
        
    def report(self):
        """Report test results."""
        logger.info("====== TEST RESULTS ======")
        logger.info(f"Total tests: {self.results['total']}")
        logger.info(f"Passed: {self.results['passed']}")
        logger.info(f"Failed: {self.results['failed']}")
        logger.info(f"Duration: {self.results['duration']:.2f} seconds")
        
        if self.results["failed"] > 0:
            logger.info("====== FAILED TESTS ======")
            for error in self.results["errors"]:
                logger.info(f"- {error['name']}: {error['error']}")


def clean_test_output():
    """Clean test output directory."""
    logger.info("Cleaning test output directory...")
    
    try:
        for item in TEST_DIR.glob("**/*"):
            if item.is_file():
                item.unlink()
        
        logger.info("Test output directory cleaned")
    except Exception as e:
        logger.error(f"Error cleaning test output: {e}")


def main():
    """Main function."""
    parser = argparse.ArgumentParser(description="Test kit for Farsiland Scraper")
    parser.add_argument("--test", dest="tests", action="append", 
                       help="Specific test to run (can be specified multiple times)")
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")
    parser.add_argument("--clean", action="store_true", help="Clean test output directory and exit")
    
    args = parser.parse_args()
    
    if args.clean:
        clean_test_output()
        return 0
        
    logger.info("===== Farsiland Scraper Test Kit =====")
    logger.info(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Create sample files
    create_sample_files()
    
    # Create test runner
    runner = TestRunner()
    
    # Add test cases
    runner.add_test(FetchTest("fetch"))
    runner.add_test(DatabaseTest("database"))
    runner.add_test(SitemapTest("sitemap"))
    runner.add_test(SeriesSpiderTest("series_spider"))
    runner.add_test(EpisodesSpiderTest("episodes_spider"))
    runner.add_test(IntegrationTest("integration"))
    
    # Run tests
    runner.run_tests(args.tests, args.debug)
    
    # Report results
    runner.report()
    
    logger.info(f"Completed at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Return non-zero exit code if any tests failed
    return 1 if runner.results["failed"] > 0 else 0


if __name__ == "__main__":
    sys.exit(main())