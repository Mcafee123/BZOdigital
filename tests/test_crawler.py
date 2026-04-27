"""Tests for the crawler module."""

import pytest

from nupla.search import _url_is_pdf


class TestUrlIsPdf:
    def test_simple_pdf(self):
        assert _url_is_pdf("https://example.ch/doc.pdf") is True

    def test_pdf_with_query_params(self):
        assert _url_is_pdf("https://example.ch/doc.pdf?fp=1") is True

    def test_pdf_with_fragment(self):
        assert _url_is_pdf("https://example.ch/doc.pdf#page=2") is True

    def test_not_pdf(self):
        assert _url_is_pdf("https://example.ch/page.html") is False

    def test_doc_endpoint_no_pdf_extension(self):
        assert _url_is_pdf("https://example.ch/_doc/12345") is False

    def test_pdf_in_path_not_extension(self):
        assert _url_is_pdf("https://example.ch/pdf-viewer/doc") is False

    def test_uppercase_pdf(self):
        assert _url_is_pdf("https://example.ch/DOC.PDF") is True
