"""Tests for BFS municipality register fuzzy matching."""

from bzodigital.bfs import Municipality, fuzzy_find_municipality


SAMPLE_MUNICIPALITIES = [
    Municipality(bfs_nr=1, name="Aeugst am Albis", canton="ZH"),
    Municipality(bfs_nr=2, name="Affoltern am Albis", canton="ZH"),
    Municipality(bfs_nr=136, name="Oberrieden", canton="ZH"),
    Municipality(bfs_nr=351, name="Köniz", canton="BE"),
    Municipality(bfs_nr=261, name="Zürich", canton="ZH"),
    Municipality(bfs_nr=2196, name="Küsnacht (BE)", canton="BE"),
    Municipality(bfs_nr=154, name="Küsnacht", canton="ZH"),
    Municipality(bfs_nr=1711, name="Köniz", canton="BE"),
]


class TestFuzzyFindMunicipality:
    def test_exact_match(self):
        results = fuzzy_find_municipality("Oberrieden", SAMPLE_MUNICIPALITIES)
        assert results[0][0].name == "Oberrieden"
        assert results[0][1] == 100

    def test_returns_canton(self):
        results = fuzzy_find_municipality("Köniz", SAMPLE_MUNICIPALITIES)
        assert results[0][0].canton == "BE"

    def test_partial_match(self):
        results = fuzzy_find_municipality("Affoltern", SAMPLE_MUNICIPALITIES)
        assert results[0][0].name == "Affoltern am Albis"
        assert results[0][1] > 70

    def test_limit(self):
        results = fuzzy_find_municipality("K", SAMPLE_MUNICIPALITIES, limit=3)
        assert len(results) <= 3

    def test_returns_bfs_nr(self):
        results = fuzzy_find_municipality("Zürich", SAMPLE_MUNICIPALITIES)
        assert results[0][0].bfs_nr == 261
