"""Tests for the rules-first PDF classifier."""

import pytest

from nupla.classify import classify_pdf, resolve_batch

# A representative DB label set — matches what db._seed_default_labels installs.
DB_LABELS = [
    "Synopse",
    "Bau- und Zonenordnung alt",
    "Bau- und Zonenordnung neu",
    "Einwendungsbericht gemäss § 7 PBG",
    "Erläuterungsbericht gemäss Art. 47 RPV",
    "Gemeindeversammlungsbeschluss",
    "Andere",
]


def _url(name: str) -> str:
    return f"https://www.oberrieden.ch/files/{name}"


class TestClassifyPdf:
    @pytest.mark.parametrize(
        "filename,title,expected",
        [
            ("erl - 3-teilrev.-bzo-ivhb-und-anderes-erlauterungsbericht-und-anhang.pdf", "", "erlauterungsbericht"),
            ("sy - 2-teilrev.-bzo-ivhb-und-anderes-synopse.pdf", "", "synopsis"),
            ("info - prasentation-infoveranstaltung-bzo-rev.pdf", "", None),
            ("öa - 1-publikationstext-off.-auflage-bzo-revision-ivhb.pdf", "", None),
            ("BZO-Revision IVHB Einwendungsbericht §7 PBG_0.pdf", "", "einwendungsbericht"),
            ("BZO-Revision IVHB Erläuternder Bericht inkl Anhang_0.pdf", "", "erlauterungsbericht"),
            ("BZO-Revision IVHB Synopse alt neu.pdf", "", "synopsis"),
            ("Gemeindeversammlungsbeschluss 25-4 BZO IVHB (1).pdf", "", "versammlungsbeschluss"),
            ("BZO Version 26. Januar 2026.pdf", "", "regulation"),
            ("aktuell 7.1-1-3-1.de.pdf", "Bau- und Zonenordnung", "regulation"),
            ("previous 7.1-1-2-1.de.pdf", "Bau- und Zonenordnung", "regulation"),
        ],
    )
    def test_filename_categories(self, filename, title, expected):
        assert classify_pdf(_url(filename), title) == expected

    def test_returns_none_for_unrelated(self):
        assert classify_pdf(_url("budget-2024.pdf"), "Gemeindebudget") is None

    def test_url_encoded_filename(self):
        assert classify_pdf(_url("Erl%C3%A4uternder%20Bericht.pdf"), "") == "erlauterungsbericht"

    def test_title_signal_only(self):
        assert classify_pdf(_url("doc-1234.pdf"), "Synopse zur BZO-Revision") == "synopsis"

    def test_publikationstext_overrides_bzo_keyword(self):
        assert classify_pdf(
            _url("öa - 1-publikationstext-off.-auflage-bzo-revision-ivhb.pdf"),
            "Publikationstext BZO-Revision",
        ) is None


class TestResolveBatch:
    def test_oberrieden_full_set(self):
        items = [
            {"url": _url("erl - 3-teilrev.-bzo-ivhb-und-anderes-erlauterungsbericht-und-anhang.pdf"), "title": ""},
            {"url": _url("sy - 2-teilrev.-bzo-ivhb-und-anderes-synopse.pdf"), "title": ""},
            {"url": _url("info - prasentation.pdf"), "title": ""},
            {"url": _url("öa - 1-publikationstext.pdf"), "title": ""},
            {"url": _url("BZO-Revision IVHB Einwendungsbericht §7 PBG.pdf"), "title": ""},
            {"url": _url("Gemeindeversammlungsbeschluss 25-4 BZO IVHB.pdf"), "title": ""},
            {"url": _url("aktuell 7.1-1-3-1.de.pdf"), "title": "Bau- und Zonenordnung"},
            {"url": _url("previous 7.1-1-2-1.de.pdf"), "title": "Bau- und Zonenordnung"},
        ]
        result = resolve_batch(items, db_labels=DB_LABELS)

        assert result[_url("erl - 3-teilrev.-bzo-ivhb-und-anderes-erlauterungsbericht-und-anhang.pdf")] == ["Erläuterungsbericht gemäss Art. 47 RPV"]
        assert result[_url("sy - 2-teilrev.-bzo-ivhb-und-anderes-synopse.pdf")] == ["Synopse"]
        # Non-classifiable items get the fallback label.
        assert result[_url("info - prasentation.pdf")] == ["Andere"]
        assert result[_url("öa - 1-publikationstext.pdf")] == ["Andere"]
        assert result[_url("BZO-Revision IVHB Einwendungsbericht §7 PBG.pdf")] == ["Einwendungsbericht gemäss § 7 PBG"]
        assert result[_url("Gemeindeversammlungsbeschluss 25-4 BZO IVHB.pdf")] == ["Gemeindeversammlungsbeschluss"]
        assert result[_url("aktuell 7.1-1-3-1.de.pdf")] == ["Bau- und Zonenordnung neu"]
        assert result[_url("previous 7.1-1-2-1.de.pdf")] == ["Bau- und Zonenordnung alt"]

    def test_single_regulation_becomes_new(self):
        items = [{"url": _url("BZO Version 26. Januar 2026.pdf"), "title": ""}]
        result = resolve_batch(items, db_labels=DB_LABELS)
        assert result[_url("BZO Version 26. Januar 2026.pdf")] == ["Bau- und Zonenordnung neu"]

    def test_two_regulations_resolved_by_year(self):
        items = [
            {"url": _url("bzo-2018.pdf"), "title": "Bau- und Zonenordnung 2018"},
            {"url": _url("bzo-2026.pdf"), "title": "Bau- und Zonenordnung 26. Januar 2026"},
        ]
        result = resolve_batch(items, db_labels=DB_LABELS)
        assert result[_url("bzo-2026.pdf")] == ["Bau- und Zonenordnung neu"]
        assert result[_url("bzo-2018.pdf")] == ["Bau- und Zonenordnung alt"]

    def test_synopsis_is_single_instance(self):
        # Two synopsis candidates → uniqueness invariant; both fall back.
        items = [
            {"url": _url("sy - synopse-a.pdf"), "title": ""},
            {"url": _url("sy - synopse-b.pdf"), "title": ""},
        ]
        result = resolve_batch(items, db_labels=DB_LABELS)
        assert result[_url("sy - synopse-a.pdf")] == ["Andere"]
        assert result[_url("sy - synopse-b.pdf")] == ["Andere"]

    def test_two_erlauterungsberichte_left_as_other(self):
        items = [
            {"url": _url("erl - bericht-a.pdf"), "title": ""},
            {"url": _url("erl - bericht-b.pdf"), "title": ""},
        ]
        result = resolve_batch(items, db_labels=DB_LABELS)
        assert result[_url("erl - bericht-a.pdf")] == ["Andere"]
        assert result[_url("erl - bericht-b.pdf")] == ["Andere"]

    def test_three_regulations_keeps_extremes(self):
        items = [
            {"url": _url("bzo-2010.pdf"), "title": "BZO 2010"},
            {"url": _url("bzo-2018.pdf"), "title": "BZO 2018"},
            {"url": _url("bzo-2026.pdf"), "title": "BZO 2026"},
        ]
        result = resolve_batch(items, db_labels=DB_LABELS)
        assert result[_url("bzo-2026.pdf")] == ["Bau- und Zonenordnung neu"]
        assert result[_url("bzo-2010.pdf")] == ["Bau- und Zonenordnung alt"]
        # The middle one falls back to Andere.
        assert result[_url("bzo-2018.pdf")] == ["Andere"]

    def test_einwendungsbericht_can_repeat(self):
        # Multiple Einwendungsberichte (e.g. one per topic) all get the label.
        items = [
            {"url": _url("Einwendungsbericht §7 PBG Teil 1.pdf"), "title": ""},
            {"url": _url("Einwendungsbericht §7 PBG Teil 2.pdf"), "title": ""},
        ]
        result = resolve_batch(items, db_labels=DB_LABELS)
        assert result[_url("Einwendungsbericht §7 PBG Teil 1.pdf")] == ["Einwendungsbericht gemäss § 7 PBG"]
        assert result[_url("Einwendungsbericht §7 PBG Teil 2.pdf")] == ["Einwendungsbericht gemäss § 7 PBG"]

    def test_empty_batch(self):
        assert resolve_batch([], db_labels=DB_LABELS) == {}

    def test_renamed_db_labels_followed_when_keywords_remain(self):
        # Operator renamed "Bau- und Zonenordnung neu" to "BZO (Neufassung)".
        # The rule "BZO (word boundary) AND substring 'neu'" still matches via
        # 'neufassung' — the classifier writes the new row's name.
        custom = [
            "Synopse",
            "Bau- und Zonenordnung alt",
            "BZO (Neufassung)",
            "Einwendungsbericht gemäss § 7 PBG",
            "Erläuterungsbericht gemäss Art. 47 RPV",
            "Gemeindeversammlungsbeschluss",
            "Andere",
        ]
        items = [{"url": _url("BZO 2026.pdf"), "title": "BZO 2026"}]
        result = resolve_batch(items, db_labels=custom)
        assert result[_url("BZO 2026.pdf")] == ["BZO (Neufassung)"]

    def test_rename_that_loses_keywords_falls_back(self):
        # Without 'zonenordnung'/'bzo' or 'neu', the substring rule misses;
        # classifier falls back to Andere.
        custom = [
            "Synopse",
            "Bau- und Zonenordnung alt",
            "Aktuelle Bauordnung",  # no zonenordnung, no bzo, no neu
            "Einwendungsbericht gemäss § 7 PBG",
            "Erläuterungsbericht gemäss Art. 47 RPV",
            "Gemeindeversammlungsbeschluss",
            "Andere",
        ]
        items = [{"url": _url("BZO 2026.pdf"), "title": "BZO 2026"}]
        result = resolve_batch(items, db_labels=custom)
        assert result[_url("BZO 2026.pdf")] == ["Andere"]

    def test_missing_andere_label_returns_empty(self):
        # If "Andere" doesn't exist in DB, unclassifiable PDFs get an empty list.
        labels_no_fallback = [l for l in DB_LABELS if l != "Andere"]
        items = [{"url": _url("budget-2024.pdf"), "title": "Budget"}]
        result = resolve_batch(items, db_labels=labels_no_fallback)
        assert result[_url("budget-2024.pdf")] == []


class TestSkipIfLabeled:
    """upsert_annotation must not stomp existing user labels when called by
    the classifier. Uses an isolated SQLite file per test."""

    @pytest.fixture
    def isolated_db(self, tmp_path, monkeypatch):
        from nupla import db

        monkeypatch.setattr(db, "DB_PATH", tmp_path / "bzo.db")
        monkeypatch.setattr(db, "engine", None)
        db.init_db()
        return db

    def test_skip_preserves_user_labels(self, isolated_db):
        db = isolated_db
        db.upsert_annotation(
            bfs_nr=1, pdf_url="http://x/a.pdf", pdf_title="A",
            labels=["manual"], selected=True,
        )
        result = db.upsert_annotation(
            bfs_nr=1, pdf_url="http://x/a.pdf", pdf_title="A (auto)",
            labels=["auto"], selected=False,
            skip_if_labeled=True,
        )
        assert result["labels"] == ["manual"]
        assert result["selected"] is True
        assert result["pdf_title"] == "A"

    def test_skip_seeds_when_no_labels(self, isolated_db):
        db = isolated_db
        db.upsert_annotation(
            bfs_nr=1, pdf_url="http://x/a.pdf", pdf_title="A",
            labels=[], selected=False,
        )
        result = db.upsert_annotation(
            bfs_nr=1, pdf_url="http://x/a.pdf", pdf_title="A",
            labels=["Synopse"], selected=False,
            skip_if_labeled=True,
        )
        assert result["labels"] == ["Synopse"]

    def test_skip_creates_when_no_row(self, isolated_db):
        db = isolated_db
        result = db.upsert_annotation(
            bfs_nr=1, pdf_url="http://x/new.pdf", pdf_title="N",
            labels=["Synopse"], selected=False,
            skip_if_labeled=True,
        )
        assert result["labels"] == ["Synopse"]
        assert result["pdf_url"] == "http://x/new.pdf"

    def test_andere_seeded_in_default_labels(self, isolated_db):
        db = isolated_db
        labels = db.get_labels()
        assert "Andere" in labels


class TestFallbackLabel:
    def test_returns_andere_when_present(self):
        from nupla.classify import fallback_label

        assert fallback_label(["Synopse", "Andere", "Other"]) == "Andere"

    def test_returns_none_when_missing(self):
        from nupla.classify import fallback_label

        assert fallback_label(["Synopse", "Bau- und Zonenordnung neu"]) is None

    def test_matches_other_or_sonstige_aliases(self):
        from nupla.classify import fallback_label

        assert fallback_label(["Synopse", "Other"]) == "Other"
        assert fallback_label(["Synopse", "Sonstige"]) == "Sonstige"


class TestSeedClassifications:
    """The api.py _seed_classifications helper auto-selects rows that get a
    real category match (anything other than the fallback label)."""

    @pytest.fixture
    def isolated_db(self, tmp_path, monkeypatch):
        from nupla import db

        monkeypatch.setattr(db, "DB_PATH", tmp_path / "bzo.db")
        monkeypatch.setattr(db, "engine", None)
        db.init_db()
        return db

    def test_real_match_is_auto_selected(self, isolated_db):
        from nupla.api import _seed_classifications

        pdfs = [
            {"url": _url("sy - synopse.pdf"), "title": ""},  # → Synopse
            {"url": _url("budget-2024.pdf"), "title": "Budget"},  # → Andere
        ]
        _seed_classifications(bfs_nr=1, pdfs=pdfs)

        anns = {a["pdf_url"]: a for a in isolated_db.get_annotations(1)}
        assert anns[_url("sy - synopse.pdf")]["selected"] is True
        assert anns[_url("sy - synopse.pdf")]["labels"] == ["Synopse"]
        assert anns[_url("budget-2024.pdf")]["selected"] is False
        assert anns[_url("budget-2024.pdf")]["labels"] == ["Andere"]

    def test_skip_if_labeled_protects_user_state(self, isolated_db):
        from nupla.api import _seed_classifications

        # User has manually deselected a synopse and replaced its label.
        isolated_db.upsert_annotation(
            bfs_nr=1, pdf_url=_url("sy - synopse.pdf"), pdf_title="",
            labels=["Andere"], selected=False,
        )
        _seed_classifications(
            bfs_nr=1,
            pdfs=[{"url": _url("sy - synopse.pdf"), "title": ""}],
        )
        ann = isolated_db.get_annotations(1)[0]
        # User edits survive — auto-classification did not stomp them.
        assert ann["labels"] == ["Andere"]
        assert ann["selected"] is False
