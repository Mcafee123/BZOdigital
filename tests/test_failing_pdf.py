"""Reproduce the failing PDF processing to find the error."""

import asyncio
import traceback
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

from nupla.converter import download_pdf, convert_pdf_stream
from nupla.enrichment import enrich_markdown_safe

URL = "https://www.oberrieden.ch/system/files/aktuell/dateien/BZO-Revision%20IVHB%20Erl%C3%A4uternder%20Bericht%20inkl.%20Anhang.pdf"


async def main():
    print("1. Downloading PDF...")
    pdf_bytes = await download_pdf(URL)
    print(f"   Downloaded {len(pdf_bytes)} bytes")

    print("2. Converting via DocConverter...")
    progress_events = []

    async def on_progress(data):
        progress_events.append(data)
        print(f"   progress: {data}")

    try:
        result = await convert_pdf_stream(pdf_bytes, "test.pdf", on_progress)
        print(f"   Done! Keys: {list(result.keys())}")
        print(f"   page_count: {result.get('page_count')}")
        print(f"   markdown length: {len(result.get('markdown', ''))}")
        print(f"   sections: {len(result.get('sections', []))}")
    except Exception as e:
        print(f"   CONVERT FAILED: {e}")
        traceback.print_exc()
        return

    print("3. Assembling markdown...")
    try:
        markdown = result.get("markdown", "")
        if not markdown:
            sections = result.get("sections", [])
            markdown = "\n\n".join(s.get("markdown", "") for s in sections)
        print(f"   Assembled {len(markdown)} chars")
    except Exception as e:
        print(f"   ASSEMBLE FAILED: {e}")
        traceback.print_exc()
        return

    print("4. Saving markdown...")
    try:
        out_path = Path("/tmp/test_failing.md")
        out_path.write_text(markdown, encoding="utf-8")
        print(f"   Saved to {out_path}")
    except Exception as e:
        print(f"   SAVE FAILED: {e}")
        traceback.print_exc()
        return

    print("5. Enriching...")
    try:
        enriched = enrich_markdown_safe(markdown)
        if enriched:
            print(f"   Enriched: {len(enriched['markdown'])} chars, {len(enriched['citations'])} citations")
        else:
            print("   Enrichment returned None")
    except Exception as e:
        print(f"   ENRICH FAILED: {e}")
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
