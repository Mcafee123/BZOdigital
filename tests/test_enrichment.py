"""Quick test to see what enrich_markdown produces."""

import sys
import re
sys.path.insert(0, "enrichment/python")

from law_enrichment import enrich_markdown
from pathlib import Path

md = Path("data/oberrieden/md/sy - 2-teilrev.-bzo-ivhb-und-anderes-synopse.md").read_text()
result = enrich_markdown(md)

# Show only resolved law citations
law_cites = [c for c in result["citations"] if c["type"] == "law" and c["is_resolved"]]
print(f"Resolved law citations: {len(law_cites)}")
for c in law_cites[:10]:
    abbr = c.get("law_abbreviation", "?")
    url = (c.get("url") or "")[:80]
    text = c["text"]
    print(f"  {text:30s} -> {abbr:10s} {url}")

# Show enriched markdown links that are law refs
links = list(re.finditer(r"\[(?:§|Art)[^\]]*\]\([^)]+\)", result["markdown"]))
print(f"\nLaw reference links in markdown: {len(links)}")
for link in links[:8]:
    text = link.group()
    if len(text) > 120:
        text = text[:120] + "..."
    print(f"  {text}")

# Show context around first law link
if links:
    m = links[0]
    start = max(0, m.start() - 80)
    end = min(len(result["markdown"]), m.end() + 80)
    snippet = result["markdown"][start:end]
    print(f"\nContext:\n  ...{snippet}...")

# Show diff between raw and enriched
print(f"\nRaw markdown length:      {len(md)}")
print(f"Enriched markdown length: {len(result['markdown'])}")
print(f"Length increase:          {len(result['markdown']) - len(md)} chars ({(len(result['markdown']) / len(md) - 1) * 100:.0f}%)")
