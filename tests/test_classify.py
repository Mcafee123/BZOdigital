"""Tests for the rules-first PDF classifier."""

import pytest

from bzodigital.classify import (
    CATEGORY_TO_LABEL,
    classify_pdf,
    resolve_batch,
)


def _url(name: str) -> str:
    return f"https://www.oberrieden.ch/files/{name}"


class TestClassifyPdf:
    @pytest.mark.parametrize(
        "filename,title,expected",
        [
            # Source filenames from data/oberrieden/src/
            ("erl - 3-teilrev.-bzo-ivhb-und-anderes-erlauterungsbericht-und-anhang.pdf", "", "erlauterungsbericht"),
            ("sy - 2-teilrev.-bzo-ivhb-und-anderes-synopse.pdf", "", "synopsis"),
            ("info - prasentation-infoveranstaltung-bzo-rev.pdf", "", None),
            ("öa - 1-publikationstext-off.-auflage-bzo-revision-ivhb.pdf", "", None),
            # Markdown-derived names from data/oberrieden/md/
            ("BZO-Revision IVHB Einwendungsbericht §7 PBG_0.pdf", "", "einwendungsbericht"),
            ("BZO-Revision IVHB Erläuternder Bericht inkl Anhang_0.pdf", "", "erlauterungsbericht"),
            ("BZO-Revision IVHB Synopse alt neu.pdf", "", "synopsis"),
            ("Gemeindeversammlungsbeschluss 25-4 BZO IVHB (1).pdf", "", "versammlungsbeschluss"),
            ("BZO Version 26. Januar 2026.pdf", "", "regulation"),
            # ZH numeric reglement IDs only become "regulation" with title context.
            ("aktuell 7.1-1-3-1.de.pdf", "Bau- und Zonenordnung", "regulation"),
            ("previous 7.1-1-2-1.de.pdf", "Bau- und Zonenordnung", "regulation"),
        ],
    )
    def test_filename_categories(self, filename, title, expected):
        assert classify_pdf(_url(filename), title) == expected

    def test_returns_none_for_unrelated(self):
        assert classify_pdf(_url("budget-2024.pdf"), "Gemeindebudget") is None

    def test_url_encoded_filename(self):
        # Real URLs may percent-encode the German "ä".
        assert classify_pdf(_url("Erl%C3%A4uternder%20Bericht.pdf"), "") == "erlauterungsbericht"

    def test_title_signal_only(self):
        # Filename gives nothing, but title carries the signal.
        assert classify_pdf(_url("doc-1234.pdf"), "Synopse zur BZO-Revision") == "synopsis"

    def test_publikationstext_overrides_bzo_keyword(self):
        # öffentliche Auflage / publication notice mentions BZO but isn't the law.
        assert classify_pdf(
            _url("öa - 1-publikationstext-off.-auflage-bzo-revision-ivhb.pdf"),
            "Publikationstext BZO-Revision",
        ) is None


class TestResolveBatch:
    def test_oberrieden_full_set(self):
        # The full oberrieden set after PDF discovery — what the user should see.
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
        result = resolve_batch(items)

        labels = {url: lbls for url, lbls in result.items()}

        assert labels[_url("erl - 3-teilrev.-bzo-ivhb-und-anderes-erlauterungsbericht-und-anhang.pdf")] == [CATEGORY_TO_LABEL["erlauterungsbericht"]]
        assert labels[_url("sy - 2-teilrev.-bzo-ivhb-und-anderes-synopse.pdf")] == [CATEGORY_TO_LABEL["synopsis"]]
        assert labels[_url("info - prasentation.pdf")] == []
        assert labels[_url("öa - 1-publikationstext.pdf")] == []
        assert labels[_url("BZO-Revision IVHB Einwendungsbericht §7 PBG.pdf")] == [CATEGORY_TO_LABEL["einwendungsbericht"]]
        assert labels[_url("Gemeindeversammlungsbeschluss 25-4 BZO IVHB.pdf")] == [CATEGORY_TO_LABEL["versammlungsbeschluss"]]
        assert labels[_url("aktuell 7.1-1-3-1.de.pdf")] == [CATEGORY_TO_LABEL["regulation_new"]]
        assert labels[_url("previous 7.1-1-2-1.de.pdf")] == [CATEGORY_TO_LABEL["regulation_old"]]

    def test_single_regulation_becomes_new(self):
        # Only one BZO file → assume it's the new revision (the user came here
        # because of a revision; the old one may be on a different page).
        items = [
            {"url": _url("BZO Version 26. Januar 2026.pdf"), "title": ""},
        ]
        result = resolve_batch(items)
        assert result[_url("BZO Version 26. Januar 2026.pdf")] == [CATEGORY_TO_LABEL["regulation_new"]]

    def test_two_regulations_resolved_by_year(self):
        items = [
            {"url": _url("bzo-2018.pdf"), "title": "Bau- und Zonenordnung 2018"},
            {"url": _url("bzo-2026.pdf"), "title": "Bau- und Zonenordnung 26. Januar 2026"},
        ]
        result = resolve_batch(items)
        assert result[_url("bzo-2026.pdf")] == [CATEGORY_TO_LABEL["regulation_new"]]
        assert result[_url("bzo-2018.pdf")] == [CATEGORY_TO_LABEL["regulation_old"]]

    def test_two_erlauterungsberichte_left_unlabelled(self):
        # Uniqueness invariant: two candidates → none labelled, user picks.
        items = [
            {"url": _url("erl - bericht-a.pdf"), "title": ""},
            {"url": _url("erl - bericht-b.pdf"), "title": ""},
        ]
        result = resolve_batch(items)
        assert result[_url("erl - bericht-a.pdf")] == []
        assert result[_url("erl - bericht-b.pdf")] == []

    def test_three_regulations_keeps_extremes(self):
        items = [
            {"url": _url("bzo-2010.pdf"), "title": "BZO 2010"},
            {"url": _url("bzo-2018.pdf"), "title": "BZO 2018"},
            {"url": _url("bzo-2026.pdf"), "title": "BZO 2026"},
        ]
        result = resolve_batch(items)
        assert result[_url("bzo-2026.pdf")] == [CATEGORY_TO_LABEL["regulation_new"]]
        assert result[_url("bzo-2010.pdf")] == [CATEGORY_TO_LABEL["regulation_old"]]
        # The middle one is left unlabelled — operator decides.
        assert result[_url("bzo-2018.pdf")] == []

    def test_empty_batch(self):
        assert resolve_batch([]) == {}


class TestSkipIfLabeled:
    """upsert_annotation must not stomp existing user labels when called by
    the classifier. Uses an isolated SQLite file per test."""

    @pytest.fixture
    def isolated_db(self, tmp_path, monkeypatch):
        from bzodigital import db

        monkeypatch.setattr(db, "DB_PATH", tmp_path / "bzo.db")
        monkeypatch.setattr(db, "engine", None)
        db.init_db()
        return db

    def test_skip_preserves_user_labels(self, isolated_db):
        db = isolated_db
        # User has manually labelled this PDF.
        db.upsert_annotation(
            bfs_nr=1, pdf_url="http://x/a.pdf", pdf_title="A",
            labels=["manual"], selected=True,
        )
        # Classifier later calls with skip_if_labeled — should be a no-op.
        result = db.upsert_annotation(
            bfs_nr=1, pdf_url="http://x/a.pdf", pdf_title="A (auto)",
            labels=["auto"], selected=False,
            skip_if_labeled=True,
        )
        assert result["labels"] == ["manual"]
        assert result["selected"] is True
        assert result["pdf_title"] == "A"  # auto title not applied

    def test_skip_seeds_when_no_labels(self, isolated_db):
        db = isolated_db
        # First classifier pass on an empty row.
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
