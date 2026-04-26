"""CLI for BZOdigital - find zoning documents for Swiss municipalities."""

import argparse
import asyncio
import sys

from dotenv import load_dotenv

from bzodigital.gemeinden import get_gemeinden
from bzodigital.profiles import DEFAULT_PROFILE, PROFILES
from bzodigital.search import (
    check_pdf_content,
    extract_pdfs,
    filter_pdfs_by_metadata,
    fuzzy_find,
    search_site,
)


def main():
    parser = argparse.ArgumentParser(description="Find BZO documents for Swiss municipalities")
    sub = parser.add_subparsers(dest="command")

    # Refresh the cached Gemeinde list
    sub.add_parser("refresh", help="Re-scrape the Gemeinde list from gpvzh.ch")

    # Search command
    search = sub.add_parser("search", help="Find BZO-related pages for a municipality")
    search.add_argument("gemeinde", help="Municipality name (fuzzy matched)")
    search.add_argument("-p", "--profile", default=DEFAULT_PROFILE, choices=PROFILES.keys(), help=f"Search profile (default: {DEFAULT_PROFILE})")
    search.add_argument("-n", "--num-matches", type=int, default=5, help="Number of fuzzy matches to show")
    search.add_argument("--pdfs", action="store_true", help="Extract and filter PDF links from result pages")
    search.add_argument("--max-results", type=int, default=50, help="Max search results to fetch (default: 50)")
    search.add_argument("--check-content", action="store_true", help="Download ambiguous PDFs to check content (requires pymupdf)")

    # List command
    sub.add_parser("list", help="List all cached Gemeinden")

    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        sys.exit(1)

    load_dotenv()
    asyncio.run(_dispatch(args))


async def _dispatch(args):
    if args.command == "refresh":
        gemeinden = await get_gemeinden(force_refresh=True)
        print(f"Cached {len(gemeinden)} Gemeinden")

    elif args.command == "list":
        gemeinden = await get_gemeinden()
        if not gemeinden:
            print("No Gemeinden cached. Run 'bzo refresh' first.")
            return
        for g in gemeinden:
            print(f"  {g['name']:30s} {g['url']}")

    elif args.command == "search":
        gemeinden = await get_gemeinden()
        if not gemeinden:
            print("No Gemeinden cached. Run 'bzo refresh' first.")
            return

        profile = PROFILES[args.profile]

        matches = fuzzy_find(args.gemeinde, gemeinden, limit=args.num_matches)
        print(f"\nFuzzy matches for '{args.gemeinde}':")
        for i, m in enumerate(matches):
            print(f"  [{i}] {m['name']} (score: {m['score']}) - {m['url']}")

        best = matches[0]
        if best["score"] < 60:
            print(f"\nBest match score too low ({best['score']}). Try a more specific name.")
            return

        print(f"\nSearching {best['url']} (profile: {args.profile})...")
        results = await search_site(best["url"], profile, max_results=args.max_results)

        if not results:
            print("No results found.")
            return

        print(f"Found {len(results)} search result(s).\n")

        if not args.pdfs:
            for r in results:
                print(f"  {r['title']}")
                print(f"  {r['url']}")
                if r.get("snippet"):
                    print(f"  {r['snippet']}")
                print()
            return

        # Extract PDFs
        print("Extracting PDFs from result pages...")
        all_pdfs: list[dict[str, str]] = []
        seen: set[str] = set()

        tasks = [extract_pdfs(r["url"]) for r in results]
        results_pdfs = await asyncio.gather(*tasks, return_exceptions=True)

        for page_pdfs in results_pdfs:
            if isinstance(page_pdfs, Exception):
                continue
            for pdf in page_pdfs:
                if pdf["url"] not in seen:
                    seen.add(pdf["url"])
                    all_pdfs.append(pdf)

        if not all_pdfs:
            print("No PDFs found on result pages.")
            return

        # Filter by metadata
        matched, ambiguous = filter_pdfs_by_metadata(all_pdfs, profile)

        # Optionally check ambiguous PDFs by content
        if args.check_content and ambiguous:
            print(f"Checking content of {len(ambiguous)} ambiguous PDF(s)...")
            content_tasks = [check_pdf_content(pdf["url"], profile) for pdf in ambiguous]
            content_results = await asyncio.gather(*content_tasks, return_exceptions=True)

            for pdf, is_match in zip(ambiguous, content_results):
                if is_match is True:
                    pdf["match"] = "content"
                    matched.append(pdf)

        print(f"\nRelevant PDFs: {len(matched)} (of {len(all_pdfs)} total)\n")
        for pdf in matched:
            if pdf.get("title"):
                print(f"  {pdf['title']}")
            print(f"  {pdf['url']}")
            print(f"  matched by: {pdf.get('match', '?')}")
            print()

        if ambiguous and not args.check_content:
            remaining = len(ambiguous) - (len(matched) - len([m for m in matched if m.get("match") == "metadata"]))
            if remaining > 0:
                print(f"  ({remaining} PDF(s) skipped — use --check-content to check by PDF content)")


if __name__ == "__main__":
    main()
