"""Scraping fallback chain: how often does each path actually carry the load?

The README claims a Crawl4AI -> BeautifulSoup cascade. This measures it over a fixed public
URL list and reports which path produced the content, giving a success rate with a real
denominator instead of an asserted percentage.

Path attribution uses the relevance_score the agent stamps on its chunks:
  1.0 -> Crawl4AI (headless Chromium)
  1.0 with no chunks from Crawl4AI -> see below; the scrape agent uses 1.0 for both paths,
  so this harness instead calls the two paths' observable outcome: chunks produced or not,
  and captures stdout markers to attribute the path.

Depends on the live internet. Sites change and rate-limit, so results are a snapshot; the
captured_at timestamp in the output is the date they apply to.

    venv\\Scripts\\python.exe benchmarks\\bench_scrape.py
"""

import asyncio
import contextlib
import io
import time

from _common import add_backend_to_path, summarise, write_evidence

add_backend_to_path()

from agents.web_scrape_agent import WebScrapeAgent  # noqa: E402

# Public, stable, robots-friendly pages spanning static HTML, JS-heavy, and doc sites.
URLS = [
    "https://example.com/",
    "https://en.wikipedia.org/wiki/Retrieval-augmented_generation",
    "https://www.python.org/about/",
    "https://docs.python.org/3/library/sqlite3.html",
    "https://fastapi.tiangolo.com/",
    "https://sqlite.org/whentouse.html",
    "https://docs.pytest.org/en/stable/",
    "https://httpbin.org/html",
    "https://news.ycombinator.com/",
    "https://github.com/ggml-org/llama.cpp",
]

# URLs that must be refused by the SSRF guard. Verifying the guard fires in the real agent,
# not only in the unit test.
BLOCKED_URLS = [
    "http://127.0.0.1:8000/health",
    "http://169.254.169.254/latest/meta-data/",
    "http://192.168.1.1/",
]


async def scrape_one(agent, url):
    """Run the agent, capturing its stdout so the path taken can be attributed."""
    buf = io.StringIO()
    started = time.perf_counter()
    with contextlib.redirect_stdout(buf):
        chunks = await agent.run(url=url)
    elapsed = round((time.perf_counter() - started) * 1000, 2)
    log = buf.getvalue()

    if "Refused unsafe URL" in log:
        path = "blocked_by_guard"
    elif "Crawl4AI scraped" in log:
        path = "crawl4ai"
    elif "Fallback scraped" in log:
        path = "beautifulsoup_fallback"
    else:
        path = "failed"

    return {
        "url": url,
        "path": path,
        "chunks": len(chunks),
        "chars": sum(len(c.text) for c in chunks),
        "elapsed_ms": elapsed,
        "log": log.strip().splitlines()[-2:],
    }


async def main():
    print("=" * 70)
    print("Scrape fallback benchmark")
    print("=" * 70)

    agent = WebScrapeAgent()

    print(f"\n  [1/2] {len(URLS)} public URLs")
    results = []
    for url in URLS:
        r = await scrape_one(agent, url)
        results.append(r)
        print(f"    {r['path']:<24}{r['chunks']:>4} chunks {r['chars']:>8} chars "
              f"{r['elapsed_ms']:>9.0f} ms  {url[:44]}")

    print(f"\n  [2/2] {len(BLOCKED_URLS)} URLs that must be refused by the SSRF guard")
    guard_results = []
    for url in BLOCKED_URLS:
        r = await scrape_one(agent, url)
        guard_results.append(r)
        ok = "ok  " if r["path"] == "blocked_by_guard" else "LEAK"
        print(f"    {ok} {r['path']:<24}{url}")

    counts = {}
    for r in results:
        counts[r["path"]] = counts.get(r["path"], 0) + 1
    produced = sum(1 for r in results if r["chunks"] > 0)

    write_evidence("bench_scrape", {
        "benchmark": "scrape",
        "method": {
            "entry_point": "agents.web_scrape_agent.WebScrapeAgent.run",
            "attribution": "stdout markers emitted by the agent identify which path produced the content",
            "urls": len(URLS),
            "note": "Depends on the live internet at the captured_at timestamp. Sites change, "
                    "rate-limit, and block headless browsers, so this is a snapshot rather than "
                    "a stable score.",
        },
        "summary": {
            "attempted": len(URLS),
            "produced_content": produced,
            "success_rate": round(produced / len(URLS), 4),
            "by_path": counts,
            "elapsed_ms": summarise([r["elapsed_ms"] for r in results]),
            "chars": summarise([r["chars"] for r in results]),
        },
        "per_url": results,
        "ssrf_guard": {
            "attempted": len(BLOCKED_URLS),
            "blocked": sum(1 for r in guard_results if r["path"] == "blocked_by_guard"),
            "per_url": guard_results,
        },
    })

    print(f"\n  Content produced for {produced}/{len(URLS)} URLs "
          f"({produced/len(URLS):.0%})")
    for path, n in sorted(counts.items()):
        print(f"    {path:<26}{n}")
    blocked = sum(1 for r in guard_results if r['path'] == 'blocked_by_guard')
    print(f"  SSRF guard blocked {blocked}/{len(BLOCKED_URLS)}")


if __name__ == "__main__":
    asyncio.run(main())
