"""
One-shot script: fetches a single SPAR API page and saves the raw JSON
so we can inspect all available fields (EAN, category, grundpreis, etc.)
"""
import json, sys, os, re
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from playwright.sync_api import sync_playwright

BASE_URL   = "https://www.spar.at"
SEARCH_URL = "https://www.spar.at/produktwelt/suche?search=&page=1"
API_HOST   = "api-scp.spar-ics.com"
OUT_FILE   = "spar_raw_hit.json"

def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=[
            "--disable-blink-features=AutomationControlled",
            "--no-sandbox",
        ])
        ctx = browser.new_context(
            viewport={"width": 1920, "height": 1080},
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            ),
            locale="de-AT",
            timezone_id="Europe/Vienna",
        )
        page = ctx.new_page()

        captured = {}

        def on_response(resp):
            try:
                if API_HOST in resp.url and "search" in resp.url and resp.status == 200:
                    data = resp.json()
                    if data.get("hits") and "paging" in data:
                        captured["url"]  = resp.url
                        captured["data"] = data
            except Exception:
                pass

        page.on("response", on_response)

        print("[*] Loading SPAR homepage…")
        page.goto(BASE_URL, wait_until="domcontentloaded", timeout=30_000)
        page.wait_for_timeout(2_000)

        print("[*] Loading search page…")
        page.goto(SEARCH_URL, wait_until="networkidle", timeout=35_000)
        page.wait_for_timeout(5_000)

        browser.close()

    if not captured:
        print("[!] Could not capture API response. Try again.")
        return

    data  = captured["data"]
    hits  = data.get("hits", [])
    if not hits:
        print("[!] No hits in response.")
        return

    hit = hits[0]
    mv  = hit.get("masterValues", {})
    geo = (mv.get("geoInformation") or [{}])[0]
    gv  = geo.get("geoValues", {})

    print(f"\n{'='*60}")
    print(f"Total hits in response: {data.get('totalHits')}")
    print(f"{'='*60}")
    print(f"\nAll masterValues keys ({len(mv)}):")
    for k in sorted(mv.keys()):
        v = mv[k]
        preview = str(v)[:80] if not isinstance(v, (list, dict)) else f"[{type(v).__name__}]"
        print(f"  {k:<45} {preview}")

    print(f"\nAll geoValues keys ({len(gv)}):")
    for k in sorted(gv.keys()):
        v = gv[k]
        preview = str(v)[:80] if not isinstance(v, (list, dict)) else f"[{type(v).__name__}]"
        print(f"  {k:<45} {preview}")

    # Save the first 3 hits in full so we can inspect nested structures
    output = {
        "api_url": captured["url"],
        "total_hits": data.get("totalHits"),
        "sample_hits": hits[:3],
    }
    with open(OUT_FILE, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    print(f"\n[✓] Full raw hits saved to {OUT_FILE}")

if __name__ == "__main__":
    main()
