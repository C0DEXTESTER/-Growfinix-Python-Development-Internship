# Automated Web Scraper for Property Listings

## Files
- `property_scraper.py` — the scraper (requests + BeautifulSoup4 + csv)
- `mock_site/listings.html` — a sample property-listings page used to demo
  the full pipeline without hitting a real, protected website
- `property_listings.csv` — sample output produced by running the script

## How it works (pipeline)
1. **Fetch** — `requests.get()` downloads the page HTML.
2. **Parse** — `BeautifulSoup` locates each listing "card" and pulls out
   the title, price, and location text.
3. **Clean**
   - Collapses whitespace/line breaks, strips leading/trailing spaces
   - Strips currency symbols/commas from prices, keeping just the number
   - Fills any missing title/price/location with `"N/A"`
   - Removes exact-duplicate listings
4. **Export** — writes a tidy `title,price,location` CSV with proper quoting
   for values containing commas.

## Run it
```bash
pip install requests beautifulsoup4
python3 property_scraper.py
```
This spins up a tiny local server for the included mock page, scrapes it,
and writes `property_listings.csv`.

## Pointing it at a REAL site
Real listing sites (Zillow, Realtor.com, 99acres, MagicBricks, etc.) are
either JavaScript-rendered, blocked by anti-bot measures, or restrict
scraping in their Terms of Service — so `requests` + `BeautifulSoup` alone
often won't work there, and scraping some of them may violate their ToS.
For any real target, check `robots.txt` and the site's terms first.

To adapt this script for a permitted site:
1. Change `TARGET_URL` at the top of `property_scraper.py` to the real URL.
2. Remove/skip the local demo-server block at the bottom (`if "localhost:8000"...`).
3. Open the real page in your browser, press F12 → Inspect a listing card,
   and update the selectors in `parse_listings()`:
   ```python
   cards = soup.find_all("div", class_="property-card")     # the listing container
   title_tag = card.find("h2", class_="property-title")     # the title element
   price_tag = card.find("span", class_="property-price")   # the price element
   location_tag = card.find("span", class_="property-location")  # the location element
   ```
   Every site uses different tag names/classes, so this is the one part
   that must be customized per-site.
4. For multi-page results, wrap `run_scraper()` in a loop over page URLs
   (e.g. `?page=1`, `?page=2`, ...) and combine the results before exporting.

## Extending the cleaning logic
- If a site lists price ranges ("$200k - $250k"), extend `clean_price()`
  to handle ranges.
- If you'd rather drop incomplete rows instead of keeping "N/A", filter
  the list in `clean_and_deduplicate()` before returning.
