"""
Pull current prices and stock for each Unmatched set from the Restoration Games
store (its public WooCommerce Store API: /wp-json/wc/store/v1/products).

Writes input/prices.json, keyed by our set names (the "set" values in input/fighters.json):
  {set: {price, currency, in_stock, stock_text, url, product}}
plus "_meta": {fetched_at, store}. Sets the store doesn't sell (e.g. Buffy, Deadpool) are absent.

Usage:  python fetch_prices.py
"""
import html
import json
import urllib.request
from datetime import datetime, timezone

STORE = "https://restorationgames.com"
PRODUCTS_URL = STORE + "/wp-json/wc/store/v1/products?search=unmatched&per_page=100&page={page}"

# Store product id -> our set name. Ids are stable; names on the store vary in punctuation.
PRODUCT_TO_SET = {
    5487: "Battle of Legends Vol. 1",
    46430: "Battle of Legends Vol. 2",
    25550202: "Battle of Legends Vol. 3",
    5494: "Robin Hood vs. Bigfoot",
    7156: "Bruce Lee",
    29500: "InGen vs. Raptors",
    54557: "Dr. Sattler vs. T-Rex",
    25953563: "Cobble & Fog",
    37392: "Beowulf vs. Little Red Riding Hood",
    50742: "Redemption Row",
    51410: "Hell's Kitchen",
    62426: "Houdini vs. The Genie",
    78228: "Teen Spirit",
    80948: "For King and Country",
    82691: "Brains and Brawn",
    88423: "Tales to Amaze",
    25547851: "Sun's Origin",
    23418082: "Slings and Arrows",
    23422742: "The Witcher: Steel and Silver",
    23422745: "The Witcher: Realms Fall",
    25552858: "Muhammad Ali vs. Bruce Lee",
    25554410: "Teenage Mutant Ninja Turtles",
    25954179: "TMNT: Shredder vs. Krang",
    25552856: "Stars and Stripes",
}

# Sets on sale that we don't have fighter data for yet (shown as "coming to the matcher").
UPCOMING_PRODUCTS = {
    25552854: "Hellboy",
    25963765: "Once Upon A Time",
}


def fetch_products():
    products, page = [], 1
    while True:
        req = urllib.request.Request(PRODUCTS_URL.format(page=page), headers={"User-Agent": "unmatched-matcher-prices-sync"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            batch = json.load(resp)
        products.extend(batch)
        if len(batch) < 100:
            return products
        page += 1


def to_entry(product):
    prices = product["prices"]
    price = int(prices["price"]) / 10 ** prices["currency_minor_unit"]
    stock = (product.get("stock_availability") or {}).get("text") or ""
    return {
        "price": price,
        "currency": prices["currency_code"],
        "in_stock": bool(product["is_in_stock"]),
        "stock_text": stock or ("In stock" if product["is_in_stock"] else "Out of stock"),
        "url": product["permalink"],
        "product": html.unescape(product["name"]),
    }


if __name__ == "__main__":
    by_id = {p["id"]: p for p in fetch_products()}

    prices, upcoming = {}, {}
    for pid, set_name in PRODUCT_TO_SET.items():
        if pid in by_id:
            prices[set_name] = to_entry(by_id[pid])
        else:
            print(f"  ! {set_name}: product {pid} not found on the store")
    for pid, name in UPCOMING_PRODUCTS.items():
        if pid in by_id:
            upcoming[name] = to_entry(by_id[pid])

    out = dict(sorted(prices.items()))
    out["_upcoming"] = upcoming
    out["_meta"] = {"fetched_at": datetime.now(timezone.utc).strftime("%Y-%m-%d"), "store": STORE}
    print(f"Priced sets: {len(prices)}, in stock: {sum(p['in_stock'] for p in prices.values())}")
    with open("input/prices.json", "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2, ensure_ascii=False)
