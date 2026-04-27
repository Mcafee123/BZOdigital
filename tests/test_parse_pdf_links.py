"""Tests for PDF link extraction using real HTML snippets from Swiss Gemeinde websites."""

from nupla.search import parse_pdf_links


BASE_URL = "https://www.example.ch/page/123"


class TestDrupalDirectPdfHref:
    """Oberrieden uses Drupal — PDFs are linked directly with .pdf in the href."""

    SNIPPET = """
    <td><a href="/system/files/aktuell/dateien/BZO%20Version%2026.%20Januar%202026.pdf">
      BZO Version 26. Januar 2026.pdf</a></td>
    <td><a href="/system/files/aktuell/dateien/BZO-Revision%20IVHB%20Synopse%20alt%20neu.pdf">
      BZO-Revision IVHB Synopse alt neu.pdf</a></td>
    <td><a href="/dienstleistungen/hochbau">Hochbau</a></td>
    """

    def test_finds_pdf_links(self):
        pdfs = parse_pdf_links(self.SNIPPET, BASE_URL)
        assert len(pdfs) == 2

    def test_resolves_relative_urls(self):
        pdfs = parse_pdf_links(self.SNIPPET, BASE_URL)
        assert pdfs[0]["url"].startswith("https://www.example.ch/")
        assert pdfs[0]["url"].endswith(".pdf")

    def test_extracts_title_from_link_text(self):
        pdfs = parse_pdf_links(self.SNIPPET, BASE_URL)
        assert "BZO Version" in pdfs[0]["title"]

    def test_ignores_non_pdf_links(self):
        pdfs = parse_pdf_links(self.SNIPPET, BASE_URL)
        urls = [p["url"] for p in pdfs]
        assert not any("hochbau" in u for u in urls)


class TestICMSTitleAttrPdf:
    """Richterswil uses iCMS — href is /_doc/{id}, PDF indicated by title="*.pdf"."""

    SNIPPET = """
    <td><a title="BZO_aktuell.pdf" href="/_doc/4649779" target="_blank">BZO_aktuell.pdf</a>
      <span class="icms-document-type-and-size"> (PDF, 1010 kB)</span></td>
    <td><a title="BZO_aktuell.pdf" href="/_doc/4649779" target="_blank"
      class="icms-btn icms-btn-primary icms-btn-block cms-download">Download</a></td>
    <td><a href="/kontakt">Kontakt</a></td>
    """

    def test_finds_pdf_by_title_attr(self):
        pdfs = parse_pdf_links(self.SNIPPET, BASE_URL)
        assert len(pdfs) == 1  # deduped by URL

    def test_url_is_doc_endpoint(self):
        pdfs = parse_pdf_links(self.SNIPPET, BASE_URL)
        assert "/_doc/4649779" in pdfs[0]["url"]

    def test_title_from_title_attr(self):
        pdfs = parse_pdf_links(self.SNIPPET, BASE_URL)
        assert pdfs[0]["title"] == "BZO_aktuell.pdf"


class TestICMSContextPdf:
    """Wädenswil uses iCMS — no .pdf in href or title, PDF indicated by (PDF, ...) after </a>."""

    SNIPPET = """
    <td><a title="700.1_Bau- und Zonenordnung Wädenswil" href="/_doc/5256772"
      target="_blank">700.1_Bau- und Zonenordnung Wädenswil</a>
      <span class="icms-document-type-and-size"> (PDF, 656 kB)</span></td>
    <td><a title="700.1_Bau- und Zonenordnung Wädenswil" href="/_doc/5256772"
      target="_blank" class="icms-btn icms-btn-primary icms-btn-block cms-download">Download</a></td>
    <td><a href="/kontakt">Kontakt</a></td>
    """

    def test_finds_pdf_by_context(self):
        pdfs = parse_pdf_links(self.SNIPPET, BASE_URL)
        assert len(pdfs) == 1  # deduped by URL

    def test_url_is_doc_endpoint(self):
        pdfs = parse_pdf_links(self.SNIPPET, BASE_URL)
        assert "/_doc/5256772" in pdfs[0]["url"]

    def test_title_from_title_attr(self):
        pdfs = parse_pdf_links(self.SNIPPET, BASE_URL)
        assert pdfs[0]["title"] == "700.1_Bau- und Zonenordnung Wädenswil"


class TestPdfHrefWithQueryParams:
    """Küsnacht — .pdf URLs with query parameters like ?fp=1."""

    SNIPPET = """
    <a href="/public/upload/assets/12951/700.1_Bau-_und_Zonenordnung.pdf?fp=1">
      Bau- und Zonenordnung</a>
    <a href="/public/upload/assets/20514/BZO_Synopse.pdf?fp=1">BZO Synopse</a>
    """

    def test_finds_pdfs_with_query_params(self):
        pdfs = parse_pdf_links(self.SNIPPET, BASE_URL)
        assert len(pdfs) == 2

    def test_preserves_query_params_in_url(self):
        pdfs = parse_pdf_links(self.SNIPPET, BASE_URL)
        assert "?fp=1" in pdfs[0]["url"]


class TestDirectPdfUrl:
    """When the page_url itself is a .pdf, extract_pdfs returns it directly.
    parse_pdf_links won't be called in that case, but we test the HTML case
    where a page links to the same PDF via absolute URL."""

    SNIPPET = """
    <a href="https://www.oberrieden.ch/system/files/aktuell/dateien/BZO%20Version%2026.%20Januar%202026.pdf">
      Download BZO</a>
    """

    def test_absolute_pdf_url(self):
        pdfs = parse_pdf_links(self.SNIPPET, BASE_URL)
        assert len(pdfs) == 1
        assert pdfs[0]["url"].startswith("https://www.oberrieden.ch/")


class TestDeduplication:
    """Same PDF linked multiple times on the same page (download button + text link)."""

    SNIPPET = """
    <td><a title="BZO_aktuell.pdf" href="/_doc/4649779" target="_blank">BZO_aktuell.pdf</a>
      <span class="icms-document-type-and-size"> (PDF, 1010 kB)</span></td>
    <td><a title="BZO_aktuell.pdf" href="/_doc/4649779" target="_blank"
      class="icms-btn icms-btn-primary icms-btn-block cms-download">Download</a></td>
    """

    def test_deduplicates_by_url(self):
        pdfs = parse_pdf_links(self.SNIPPET, BASE_URL)
        assert len(pdfs) == 1


class TestMixedSignals:
    """Page with a mix of PDF types and non-PDF links."""

    SNIPPET = """
    <a href="/files/bzo.pdf">BZO Dokument</a>
    <a title="Synopse.pdf" href="/_doc/12345" target="_blank">Synopse</a>
    <a title="Zonenplan" href="/_doc/67890" target="_blank">Zonenplan</a>
      <span> (PDF, 2.3 MB)</span>
    <a href="/kontakt">Kontakt</a>
    <a href="/news">News</a>
    <a href="/files/image.png">Bild</a>
    """

    def test_finds_all_three_pdf_types(self):
        pdfs = parse_pdf_links(self.SNIPPET, BASE_URL)
        assert len(pdfs) == 3

    def test_ignores_non_pdf_links(self):
        pdfs = parse_pdf_links(self.SNIPPET, BASE_URL)
        urls = [p["url"] for p in pdfs]
        assert not any("kontakt" in u or "news" in u or "image" in u for u in urls)


class TestNoPdfs:
    """Page with no PDF links at all."""

    SNIPPET = """
    <a href="/kontakt">Kontakt</a>
    <a href="/news">Aktuelles</a>
    <a href="https://www.google.ch">Google</a>
    """

    def test_returns_empty(self):
        pdfs = parse_pdf_links(self.SNIPPET, BASE_URL)
        assert pdfs == []
