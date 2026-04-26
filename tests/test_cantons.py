"""Tests for canton registry and URL lookup."""

from bzodigital.cantons import SCRAPERS, find_url


SAMPLE_CANTON_DATA = [
    {"name": "Adliswil", "url": "http://www.adliswil.ch/"},
    {"name": "Oberrieden", "url": "http://www.oberrieden.ch/"},
    {"name": "Küsnacht", "url": "http://www.kuesnacht.ch/"},
    {"name": "Aeugst a.A.", "url": "http://www.aeugst-albis.ch/"},
]


class TestScraperRegistry:
    def test_zh_registered(self):
        assert "zh" in SCRAPERS

    def test_scraper_is_callable(self):
        assert callable(SCRAPERS["zh"])


class TestFindUrl:
    def test_exact_match(self):
        url = find_url("Oberrieden", SAMPLE_CANTON_DATA)
        assert url == "http://www.oberrieden.ch/"

    def test_fuzzy_match_bfs_vs_scraper_name(self):
        """BFS uses 'Aeugst am Albis' but scraper has 'Aeugst a.A.'"""
        url = find_url("Aeugst am Albis", SAMPLE_CANTON_DATA)
        assert url == "http://www.aeugst-albis.ch/"

    def test_no_match_returns_none(self):
        url = find_url("Nonexistent Village", SAMPLE_CANTON_DATA)
        assert url is None

    def test_empty_data_returns_none(self):
        url = find_url("Oberrieden", [])
        assert url is None
