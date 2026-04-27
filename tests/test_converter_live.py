"""Quick smoke test for the converter module against the live DocConverter API."""

import asyncio
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

from nupla.pipeline.converter import convert_pdf_stream, _base_url


async def main():
    pdf_path = Path("data/oberrieden/src/öa - 1-publikationstext-off.-auflage-bzo-revision-ivhb.pdf")
    pdf_bytes = pdf_path.read_bytes()

    progress_events = []

    async def on_progress(data):
        progress_events.append(data)
        print(f"  progress: {data}")

    print(f"URL: {_base_url()}")
    print(f"Uploading {len(pdf_bytes)} bytes as {pdf_path.name}...")

    result = await convert_pdf_stream(pdf_bytes, pdf_path.name, on_progress)

    print(f"Done! Pages: {result.get('page_count')}")
    print(f"Progress events received: {len(progress_events)}")
    print(f"Markdown length: {len(result.get('markdown', ''))}")
    print(f"Sections: {len(result.get('sections', []))}")
    meta = result.get("metadata", {})
    print(f"Summary: {meta.get('summary', '')[:120]}")

    sections = result.get("sections", [])
    total_section_md = sum(len(s.get("markdown", "")) for s in sections)
    print(f"Total section markdown: {total_section_md} chars")


if __name__ == "__main__":
    asyncio.run(main())
