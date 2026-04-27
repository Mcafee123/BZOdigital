"""Tests for domain inference from search results."""

from nupla.pipeline.search import infer_domain


class TestInferDomain:
    def test_picks_most_common_ch_domain(self):
        results = [
            {"url": "https://www.oberrieden.ch/page1"},
            {"url": "https://www.oberrieden.ch/page2"},
            {"url": "https://www.oberrieden.ch/page3"},
            {"url": "https://de.wikipedia.org/wiki/Oberrieden"},
        ]
        assert infer_domain(results) == "www.oberrieden.ch"

    def test_filters_noise_domains(self):
        results = [
            {"url": "https://de.wikipedia.org/wiki/Oberrieden"},
            {"url": "https://de.wikipedia.org/wiki/BZO"},
            {"url": "https://www.oberrieden.ch/page1"},
        ]
        assert infer_domain(results) == "www.oberrieden.ch"

    def test_prefers_ch_domain(self):
        results = [
            {"url": "https://www.example.com/page1"},
            {"url": "https://www.example.com/page2"},
            {"url": "https://www.koeniz.ch/page1"},
        ]
        assert infer_domain(results) == "www.koeniz.ch"

    def test_empty_results(self):
        assert infer_domain([]) is None

    def test_only_noise_domains(self):
        results = [
            {"url": "https://de.wikipedia.org/wiki/Something"},
            {"url": "https://www.facebook.com/something"},
        ]
        assert infer_domain(results) is None
