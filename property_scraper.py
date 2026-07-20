"""
Automated Web Scraper for Property Listings
=============================================
Tech stack: Python, Requests, BeautifulSoup4, csv

What this script does:
    1. Fetches a page of real-estate listings (HTML) using `requests`.
    2. Parses the HTML with `BeautifulSoup` to pull out each listing's
       title, price, and location.
    3. Cleans the raw text (extra whitespace, currency symbols, commas,
       missing fields, duplicate listings).
    4. Exports the cleaned data to a neatly formatted CSV file.

IMPORTANT - about the target site:
    Major real-estate platforms (Zillow, Realtor.com, Trulia, 99acres,
    MagicBricks, etc.) render listings with JavaScript and actively block
    simple `requests`-based scrapers (CAPTCHAs, IP bans, ToS restrictions).

    So this script is built and tested against a small local mock listings
    page (mock_site/listings.html) that mirrors a typical real-estate
    site's HTML structure. This lets you see the full pipeline run
    successfully end-to-end.

    To point this at a REAL site, you only need to change two things:
        (1) the `TARGET_URL` below
        (2) the CSS selectors in `parse_listings()` to match that site's
            actual HTML (use your browser's "Inspect Element" to find them)
    Everything else (cleaning, CSV export) stays the same.
"""

import csv
import re
import sys
import time
import threading
import http.server
import socketserver
from pathlib import Path

import requests
from bs4 import BeautifulSoup

# ---------------------------------------------------------------------------
# CONFIG - change these to point at a real site
# ---------------------------------------------------------------------------
TARGET_URL = "http://localhost:8000/listings.html"   # <-- swap for a real listings URL
OUTPUT_CSV = "property_listings.csv"
REQUEST_HEADERS = {
    # A realistic User-Agent header. Real sites often reject requests
    # that don't look like they're coming from a browser.
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    )
}
REQUEST_TIMEOUT = 10  # seconds


# ---------------------------------------------------------------------------
# STEP 1: FETCH
# ---------------------------------------------------------------------------
def fetch_page(url: str) -> str:
    """Download the HTML for a given URL using requests."""
    response = requests.get(url, headers=REQUEST_HEADERS, timeout=REQUEST_TIMEOUT)
    response.raise_for_status()  # raises an exception on 4xx/5xx responses
    return response.text


# ---------------------------------------------------------------------------
# STEP 2: PARSE
# ---------------------------------------------------------------------------
def parse_listings(html: str) -> list[dict]:
    """
    Extract raw (uncleaned) title/price/location for every listing card.

    NOTE: The class names below ("property-card", "property-title", etc.)
    match the MOCK site. For a real site, open DevTools (F12), inspect a
    listing card, and swap these selectors for the real ones.
    """
    soup = BeautifulSoup(html, "html.parser")
    cards = soup.find_all("div", class_="property-card")

    raw_listings = []
    for card in cards:
        title_tag = card.find("h2", class_="property-title")
        price_tag = card.find("span", class_="property-price")
        location_tag = card.find("span", class_="property-location")

        raw_listings.append({
            "title": title_tag.get_text() if title_tag else None,
            "price": price_tag.get_text() if price_tag else None,
            "location": location_tag.get_text() if location_tag else None,
        })

    return raw_listings


# ---------------------------------------------------------------------------
# STEP 3: CLEAN
# ---------------------------------------------------------------------------
def clean_text(value: str | None) -> str:
    """Collapse whitespace/newlines and strip leading/trailing spaces."""
    if value is None:
        return "N/A"
    cleaned = re.sub(r"\s+", " ", value).strip()
    return cleaned if cleaned else "N/A"


def clean_price(value: str | None) -> str:
    """
    Normalize price text into a plain numeric string, e.g.:
        "$ 245,000"      -> "245000"
        "$1,250,000 "    -> "1250000"
        "$98,750.00"     -> "98750.00"
        "Contact for Price" -> "N/A"
        None             -> "N/A"
    """
    if value is None:
        return "N/A"
    text = clean_text(value)
    match = re.search(r"[\d,]+(?:\.\d+)?", text)
    if not match:
        return "N/A"  # e.g. "Contact for Price" has no digits
    return match.group().replace(",", "")


def clean_listing(raw: dict) -> dict:
    return {
        "title": clean_text(raw["title"]),
        "price": clean_price(raw["price"]),
        "location": clean_text(raw["location"]),
    }


def clean_and_deduplicate(raw_listings: list[dict]) -> list[dict]:
    cleaned = [clean_listing(item) for item in raw_listings]

    # Drop exact duplicate listings (same title + price + location)
    seen = set()
    deduped = []
    for row in cleaned:
        key = (row["title"], row["price"], row["location"])
        if key not in seen:
            seen.add(key)
            deduped.append(row)
    return deduped


# ---------------------------------------------------------------------------
# STEP 4: EXPORT TO CSV
# ---------------------------------------------------------------------------
def export_to_csv(listings: list[dict], filename: str) -> None:
    fieldnames = ["title", "price", "location"]
    with open(filename, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(listings)


# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------
def run_scraper(url: str, output_path: str) -> None:
    print(f"Fetching: {url}")
    html = fetch_page(url)

    print("Parsing listings...")
    raw_listings = parse_listings(html)
    print(f"  -> Found {len(raw_listings)} raw listing(s)")

    print("Cleaning data...")
    listings = clean_and_deduplicate(raw_listings)
    print(f"  -> {len(listings)} listing(s) after cleaning/dedup")

    print(f"Exporting to {output_path} ...")
    export_to_csv(listings, output_path)
    print("Done.")

    print("\nPreview:")
    for row in listings:
        print(f"  - {row['title']} | ${row['price']} | {row['location']}")


# ---------------------------------------------------------------------------
# Local demo server (only used so this script is runnable out-of-the-box
# against the included mock_site/listings.html). Remove this block when
# pointing TARGET_URL at a real, live website.
# ---------------------------------------------------------------------------
def _start_demo_server(directory: str, port: int = 8000):
    handler = lambda *args, **kwargs: http.server.SimpleHTTPRequestHandler(
        *args, directory=directory, **kwargs
    )
    httpd = socketserver.TCPServer(("localhost", port), handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    return httpd


if __name__ == "__main__":
    demo_dir = Path(__file__).parent / "mock_site"
    httpd = None

    if "localhost:8000" in TARGET_URL and demo_dir.exists():
        httpd = _start_demo_server(str(demo_dir))
        time.sleep(0.3)  # give the server a moment to spin up

    try:
        run_scraper(TARGET_URL, OUTPUT_CSV)
    except requests.exceptions.RequestException as e:
        print(f"Network/request error: {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        if httpd:
            httpd.shutdown()
