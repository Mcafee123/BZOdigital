"""CLI for BZOdigital - find zoning documents for Swiss municipalities."""

import argparse
import asyncio
import sys

from dotenv import load_dotenv

from bzodigital.bfs import fuzzy_find_municipality, load_bfs, update_bfs_register
from bzodigital.cantons import find_url, get_canton
from bzodigital.db import init_db
from bzodigital.profiles import DEFAULT_PROFILE, PROFILES
from bzodigital.search import (
    check_pdf_content,
    extract_pdfs,
    filter_pdfs_by_metadata,
    has_serper_key,
    infer_domain,
    search_or_crawl_open,
    search_or_crawl_site,
)


def main():
    parser = argparse.ArgumentParser(description="Find BZO documents for Swiss municipalities")
    sub = parser.add_subparsers(dest="command")

    # BFS register update
    sub.add_parser("bfs-update", help="Download/update the BFS municipality register")

    # Refresh canton scraper
    refresh = sub.add_parser("refresh", help="Re-scrape a canton's Gemeinde list")
    refresh.add_argument("--canton", default="zh", help="Canton ID to refresh (default: zh)")

    # Search command
    search = sub.add_parser("search", help="Find BZO-related pages for a municipality")
    search.add_argument("gemeinde", help="Municipality name (fuzzy matched)")
    search.add_argument("-p", "--profile", default=DEFAULT_PROFILE, choices=PROFILES.keys(), help=f"Search profile (default: {DEFAULT_PROFILE})")
    search.add_argument("-n", "--num-matches", type=int, default=5, help="Number of fuzzy matches to show")
    search.add_argument("--pdfs", action="store_true", help="Extract and filter PDF links from result pages")
    search.add_argument("--max-results", type=int, default=50, help="Max search results to fetch (default: 50)")
    search.add_argument("--check-content", action="store_true", help="Download ambiguous PDFs to check content (requires pymupdf)")

    # List command
    list_cmd = sub.add_parser("list", help="List municipalities")
    list_cmd.add_argument("--canton", help="Filter by canton (e.g. ZH, BE)")

    # Serve command
    serve = sub.add_parser("serve", help="Start the REST API server")
    serve.add_argument("--host", default="0.0.0.0", help="Host to bind to")
    serve.add_argument("--port", type=int, default=8000, help="Port to bind to")

    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        sys.exit(1)

    load_dotenv()

    if args.command == "serve":
        import uvicorn
        uvicorn.run("bzodigital.api:app", host=args.host, port=args.port, reload=True)
    else:
        asyncio.run(_dispatch(args))


async def _dispatch(args):
    init_db()

    if args.command == "bfs-update":
        path = await update_bfs_register()
        municipalities = load_bfs()
        print(f"Updated BFS register: {len(municipalities)} municipalities -> {path}")

    elif args.command == "refresh":
        canton_data = await get_canton(args.canton, force_refresh=True)
        if canton_data is None:
            print(f"No scraper registered for canton '{args.canton}'.")
            return
        print(f"Cached {len(canton_data)} Gemeinden for {args.canton.upper()}")

    elif args.command == "list":
        municipalities = load_bfs()
        if not municipalities:
            print("BFS register not found. Run 'bzo bfs-update' first.")
            return
        if args.canton:
            municipalities = [m for m in municipalities if m.canton.upper() == args.canton.upper()]
        for m in municipalities:
            print(f"  {m.name:30s} {m.canton}  (BFS {m.bfs_nr})")
        print(f"\n  {len(municipalities)} municipalities")

    elif args.command == "search":
        municipalities = load_bfs()
        if not municipalities:
            print("BFS register not found. Run 'bzo bfs-update' first.")
            return

        profile = PROFILES[args.profile]
        method = "Serper" if has_serper_key() else "Crawler"

        # Step 1: Find the municipality in BFS
        matches = fuzzy_find_municipality(args.gemeinde, municipalities, limit=args.num_matches)
        print(f"\nMatches for '{args.gemeinde}':")
        for i, (muni, score) in enumerate(matches):
            print(f"  [{i}] {muni.name} ({muni.canton}) — score: {score}")

        best_muni, best_score = matches[0]
        if best_score < 60:
            print(f"\nBest match score too low ({best_score}). Try a more specific name.")
            return

        # Step 2: Try canton URL mapping
        canton_data = await get_canton(best_muni.canton.lower())
        base_url = None
        if canton_data:
            base_url = find_url(best_muni.name, canton_data)

        # Step 3: Search or crawl
        if base_url:
            print(f"\n[{method}] Searching {base_url} (via {best_muni.canton} mapping)...")
            results = await search_or_crawl_site(base_url, profile, max_results=args.max_results)
        else:
            print(f"\nNo URL mapping for {best_muni.canton}. [{method}] Searching for '{best_muni.name}'...")
            results = await search_or_crawl_open(best_muni.name, None, profile, max_results=args.max_results)
            domain = infer_domain(results)
            if domain:
                print(f"  (dominant domain: {domain})")

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
