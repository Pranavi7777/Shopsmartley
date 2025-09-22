"""
Robust price_fetcher with optional Playwright support and requests+BeautifulSoup fallback.
Exports:
 - fetch_price(url) -> float|None
 - update_all_prices() -> updates DB from vendor URLs
"""
import re
import time
from urllib.parse import urlparse
import os  # <-- CHANGE: Import the os module

# <-- CHANGE: Remove the old, hardcoded DB config.
# DB_HOST = "localhost"
# DB_NAME = "postgres"
# DB_USER = "postgres"
# DB_PASSWORD = "admin"

# <-- CHANGE: Get the database connection string from the environment variable.
# This ensures it works both locally (with a fallback) and on Render.
DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://postgres:admin@localhost/postgres")


# DB dependency imported lazily to avoid import-time errors in environments without psycopg2
def get_db_connection():
    import psycopg2
    # <-- CHANGE: Connect using the single DATABASE_URL string.
    return psycopg2.connect(DATABASE_URL)

def extract_number(text):
    if not text:
        return None
    # find first number-like token (handles commas/periods)
    m = re.search(r'[\d\.,]+', text.replace('\xa0', ' '))
    if not m:
        return None
    num = m.group(0).replace(',', '')
    try:
        return float(num)
    except Exception:
        return None

# Try Playwright first; if not available, fall back to requests + BeautifulSoup
USE_PLAYWRIGHT = False
try:
    from playwright.sync_api import sync_playwright  # type: ignore
    USE_PLAYWRIGHT = True
except Exception:
    USE_PLAYWRIGHT = False
    import requests  # type: ignore
    from bs4 import BeautifulSoup  # type: ignore


def fetch_price_playwright(url, timeout=15000):
    """Fetch page with Playwright and try domain-specific selectors, fallback to body text."""
    from playwright.sync_api import sync_playwright  # Import inside function
    parsed = urlparse(url)
    domain = parsed.netloc.lower()
    price_text = None

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        try:
            page.goto(url, timeout=timeout)
            # domain-specific selectors
            if "amazon." in domain:
                selectors = ["#priceblock_ourprice", "#priceblock_dealprice", "#price_inside_buybox", ".a-color-price"]
            elif "flipkart." in domain:
                selectors = ["._30jeq3._16Jk6d", "._1vC4OE"]
            elif "apple." in domain or "hp." in domain:
                selectors = [".price", ".product-price", ".offer-price", "[itemprop=price]"]
            else:
                selectors = ["meta[itemprop='price']", "[class*=price]", "[id*=price]", "body"]

            for sel in selectors:
                try:
                    el = page.query_selector(sel)
                    if el:
                        txt = el.inner_text().strip()
                        if txt:
                            price_text = txt
                            break
                except Exception:
                    continue

            # fallback: read entire page text and extract first number
            if not price_text:
                body = page.locator("body").inner_text()
                price_text = body

        except Exception:
            try:
                browser.close()
            except Exception:
                pass
            return None
        try:
            browser.close()
        except Exception:
            pass

    return extract_number(price_text)
def fetch_price_requests(url, timeout=15):
    """Fetch page using requests + BeautifulSoup and try common selectors, fallback to whole text."""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0 Safari/537.36"
    }
    try:
        resp = requests.get(url, headers=headers, timeout=timeout)
        resp.raise_for_status()
    except Exception:
        return None

    soup = BeautifulSoup(resp.text, "lxml")
    domain = urlparse(url).netloc.lower()
    price_text = None

    if "amazon." in domain:
        selectors = ["#priceblock_ourprice", "#priceblock_dealprice", "#price_inside_buybox", ".a-color-price"]
    elif "flipkart." in domain:
        selectors = ["._30jeq3._16Jk6d", "._1vC4OE"]
    elif "apple." in domain or "hp." in domain:
        selectors = [".price", ".product-price", ".offer-price", "[itemprop=price]"]
    else:
        selectors = ["meta[itemprop='price']", "[class*=price]", "[id*=price]"]

    for sel in selectors:
        try:
            el = soup.select_one(sel)
            if el:
                price_text = el.get_text().strip()
                break
        except Exception:
            continue

    if not price_text:
        text = soup.get_text(separator=' ')
        price_text = text

    return extract_number(price_text)

def fetch_price(url):
    """Public: returns price (float) or None. Uses Playwright if available else requests+BS4."""
    if not url:
        return None
    try:
        if USE_PLAYWRIGHT:
            return fetch_price_playwright(url)
        else:
            return fetch_price_requests(url)
    except Exception:
        return None

def update_all_prices():
    """Read product/vendor links from DB and update product_prices with current fetched price."""
    conn = get_db_connection()
    cur = conn.cursor()
    # get products and vendor urls from DB
    cur.execute("""
        SELECT p.product_id, p.product_name, v.vendor_id, v.vendor_name, v.website_url
        FROM products p
        JOIN product_prices pp ON pp.product_id = p.product_id
        JOIN vendors v ON pp.vendor_id = v.vendor_id
        GROUP BY p.product_id, p.product_name, v.vendor_id, v.vendor_name, v.website_url
    """)
    rows = cur.fetchall()
    cur.close()
    conn.close()

    if not rows:
        return

    for product_id, product_name, vendor_id, vendor_name, website_url in rows:
        if not website_url:
            continue
        try:
            price = fetch_price(website_url)
        except Exception:
            price = None

        if price is None:
            # couldn't determine price for this URL
            continue

        conn = get_db_connection()
        cur = conn.cursor()
        # update existing product_prices row or insert if missing (should exist)
        cur.execute("""
            SELECT price_id FROM product_prices
            WHERE product_id = %s AND vendor_id = %s
        """, (product_id, vendor_id))
        r = cur.fetchone()
        if r:
            cur.execute("UPDATE product_prices SET product_price = %s WHERE price_id = %s", (price, r[0]))
        else:
            cur.execute("INSERT INTO product_prices(product_id, vendor_id, product_price) VALUES (%s, %s, %s)", (product_id, vendor_id, price))
        conn.commit()
        cur.close()
        conn.close()
        # small delay to be polite
        time.sleep(1)

if __name__ == "__main__":
    update_all_prices()