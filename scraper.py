"""
OEM Parts Online - Air Bag System Parts Scraper
================================================
Her marka icin Air Bag System kategorisindeki tum parcalari ceker.
Her marka icin ayri JSON dosyasi olusturur.
GitHub Actions ile paralel calistirilabilir.

Kullanim:
  python scraper.py Honda               # Sadece Honda
  python scraper.py Honda, Toyota       # Honda ve Toyota
  python scraper.py                     # Tum markalar (sirayla)
  python scraper.py Honda --reset       # Sifirdan basla
"""

import cloudscraper
from bs4 import BeautifulSoup
import time
import math
import os
import json
import sys
import random
from datetime import datetime

sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

BRANDS = [
    "Acura", "Audi", "BMW", "Ford", "GM", "Honda", "Hyundai",
    "Infiniti", "Jaguar", "Kia", "Land Rover", "Lexus", "Mazda",
    "Mitsubishi", "Mopar", "Nissan", "Porsche", "Subaru",
    "Toyota", "Volkswagen", "Volvo"
]

CATEGORY_FILTER = "Electrical%252C%2BLighting%2Band%2BBody%253EAir%2BBag%2BSystem"
SEARCH_TERM = "air+bag"
ITEMS_PER_PAGE = 18
REQUEST_DELAY = 2
RETRY_COUNT = 5
RETRY_DELAY = 15

OUTPUT_DIR = "output"
PROGRESS_DIR = os.path.join(OUTPUT_DIR, "progress")

BROWSER_CONFIGS = [
    {'browser': 'chrome', 'platform': 'windows', 'desktop': True},
    {'browser': 'chrome', 'platform': 'linux', 'desktop': True},
    {'browser': 'firefox', 'platform': 'windows', 'desktop': True},
    {'browser': 'firefox', 'platform': 'linux', 'desktop': True},
]


def p(msg):
    print(msg, flush=True)


def get_subdomain(brand: str) -> str:
    return brand.lower().replace(" ", "")


def brand_filename(brand: str) -> str:
    return get_subdomain(brand) + ".json"


def build_url(brand: str, page: int) -> str:
    sub = get_subdomain(brand)
    return (
        f"https://{sub}.oempartsonline.com/search"
        f"?autocareCategories={CATEGORY_FILTER}"
        f"&search_str={SEARCH_TERM}"
        f"&page={page}"
    )


def new_scraper(config_index=None):
    if config_index is None:
        config_index = random.randint(0, len(BROWSER_CONFIGS) - 1)
    cfg = BROWSER_CONFIGS[config_index % len(BROWSER_CONFIGS)]
    scraper = cloudscraper.create_scraper(
        browser=cfg,
        delay=random.uniform(3, 6),
    )
    scraper.headers.update({
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.9',
        'Accept-Encoding': 'gzip, deflate, br',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
        'Sec-Fetch-Dest': 'document',
        'Sec-Fetch-Mode': 'navigate',
        'Sec-Fetch-Site': 'none',
        'Sec-Fetch-User': '?1',
        'Cache-Control': 'max-age=0',
    })
    return scraper


def fetch(scraper, url: str):
    for attempt in range(1, RETRY_COUNT + 1):
        try:
            time.sleep(random.uniform(0.5, 2.0))
            resp = scraper.get(url, timeout=30)
            if resp.status_code == 200:
                if 'Cloudflare' in resp.text and 'blocked' in resp.text.lower():
                    p(f"    [!] Cloudflare soft-block (deneme {attempt}/{RETRY_COUNT})")
                else:
                    return resp.text, scraper
            else:
                p(f"    [!] HTTP {resp.status_code} (deneme {attempt}/{RETRY_COUNT})")

            if attempt < RETRY_COUNT:
                wait = RETRY_DELAY * attempt + random.uniform(0, 10)
                p(f"    Yeni session olusturuluyor, {wait:.0f}s bekleniyor...")
                time.sleep(wait)
                scraper = new_scraper(attempt)
        except Exception as e:
            p(f"    [!] Hata: {e} (deneme {attempt}/{RETRY_COUNT})")
            if attempt < RETRY_COUNT:
                wait = RETRY_DELAY * attempt
                time.sleep(wait)
                scraper = new_scraper(attempt)
    return None, scraper


def get_total(soup: BeautifulSoup) -> int:
    el = soup.select_one('span.result-count')
    if el:
        try:
            return int(el.get_text(strip=True).replace(',', '').replace('.', ''))
        except ValueError:
            pass
    return 0


def parse_page(soup: BeautifulSoup, brand: str) -> list[dict]:
    parts = []
    sub = get_subdomain(brand)

    for card in soup.select('div.catalog-product-card'):
        pn_a = card.select_one('span.catalog-product-id a')
        if not pn_a:
            continue

        title_a = card.select_one('h2.product-title a')
        desc_div = card.select_one('div.catalog-product-card-description')

        part_number = pn_a.get_text(strip=True)
        href = pn_a.get('href', '')
        title = title_a.get_text(strip=True) if title_a else ''
        desc = desc_div.get_text(strip=True) if desc_div else ''

        sale_price = ''
        msrp = ''
        sp_el = card.select_one('.sale-pricing')
        if sp_el:
            sale_price = sp_el.get_text(strip=True)
        msrp_el = card.select_one('.list-price-value')
        if msrp_el:
            msrp = msrp_el.get_text(strip=True)

        full_url = f"https://{sub}.oempartsonline.com{href}" if href.startswith('/') else href

        parts.append({
            'brand': brand,
            'part_number': part_number,
            'title': title,
            'description': desc,
            'sale_price': sale_price,
            'msrp': msrp,
            'url': full_url,
        })

    return parts


def load_progress(brand: str) -> dict:
    path = os.path.join(PROGRESS_DIR, f"{get_subdomain(brand)}.json")
    if os.path.exists(path):
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}


def save_progress(brand: str, data: dict):
    path = os.path.join(PROGRESS_DIR, f"{get_subdomain(brand)}.json")
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def load_brand_data(brand: str) -> list[dict]:
    path = os.path.join(OUTPUT_DIR, brand_filename(brand))
    if os.path.exists(path) and os.path.getsize(path) > 0:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    return []


def save_brand_data(brand: str, data: list[dict]):
    path = os.path.join(OUTPUT_DIR, brand_filename(brand))
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def scrape_brand(scraper, brand: str, reset: bool = False):
    progress = {} if reset else load_progress(brand)
    all_parts = [] if reset else load_brand_data(brand)

    if progress.get('completed'):
        p(f"  [{brand}] zaten tamamlanmis, atlaniyor.")
        return progress.get('scraped_count', 0), scraper

    start_page = progress.get('last_page', 0) + 1
    total = progress.get('total_results')
    scraped = progress.get('scraped_count', 0)

    if total is None:
        p(f"  [{brand}] Kontrol ediliyor...")
        time.sleep(random.uniform(2, 5))
        html, scraper = fetch(scraper, build_url(brand, 1))
        if not html:
            p(f"  [{brand}] Baglanti basarisiz, atlaniyor.")
            return 0, scraper

        soup = BeautifulSoup(html, 'lxml')
        total = get_total(soup)
        if total == 0:
            p(f"  [{brand}] Sonuc bulunamadi.")
            save_progress(brand, {'completed': True, 'total_results': 0, 'scraped_count': 0, 'last_page': 0})
            save_brand_data(brand, [])
            return 0, scraper

        pages = math.ceil(total / ITEMS_PER_PAGE)
        p(f"  [{brand}] {total} sonuc ({pages} sayfa)")

        if start_page == 1:
            rows = parse_page(soup, brand)
            all_parts.extend(rows)
            scraped += len(rows)
            save_brand_data(brand, all_parts)
            p(f"    Sayfa 1/{pages} -> {len(rows)} parca (toplam: {scraped})")
            save_progress(brand, {
                'total_results': total, 'last_page': 1,
                'scraped_count': scraped, 'completed': pages <= 1
            })
            start_page = 2
            time.sleep(REQUEST_DELAY)
    else:
        pages = math.ceil(total / ITEMS_PER_PAGE)
        p(f"  [{brand}] Devam: sayfa {start_page}/{pages}")

    for pg in range(start_page, pages + 1):
        html, scraper = fetch(scraper, build_url(brand, pg))
        if not html:
            p(f"    Sayfa {pg} basarisiz, marka atlaniyor.")
            break

        soup = BeautifulSoup(html, 'lxml')
        rows = parse_page(soup, brand)
        all_parts.extend(rows)
        scraped += len(rows)
        save_brand_data(brand, all_parts)

        p(f"    Sayfa {pg}/{pages} -> {len(rows)} parca (toplam: {scraped})")
        save_progress(brand, {
            'total_results': total, 'last_page': pg,
            'scraped_count': scraped, 'completed': pg >= pages
        })

        if not rows:
            prog = load_progress(brand)
            prog['completed'] = True
            save_progress(brand, prog)
            break

        time.sleep(REQUEST_DELAY + random.uniform(0.5, 2.0))

    final = load_progress(brand)
    if final.get('completed'):
        p(f"  [{brand}] Tamamlandi! {scraped} parca -> {brand_filename(brand)}")

    return scraped, scraper


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    os.makedirs(PROGRESS_DIR, exist_ok=True)

    raw = [a for a in sys.argv[1:] if not a.startswith('--')]
    flags = [a for a in sys.argv[1:] if a.startswith('--')]
    reset = '--reset' in flags

    brands = BRANDS
    if raw:
        wanted = [x.strip().lower() for x in " ".join(raw).split(",")]
        brands = [b for b in BRANDS if b.lower() in wanted]
        if not brands:
            p(f"Gecersiz marka! Secenekler: {', '.join(BRANDS)}")
            sys.exit(1)

    if reset:
        for b in brands:
            sub = get_subdomain(b)
            for path in [
                os.path.join(OUTPUT_DIR, f"{sub}.json"),
                os.path.join(PROGRESS_DIR, f"{sub}.json"),
            ]:
                if os.path.exists(path):
                    os.remove(path)
        p("Ilerleme sifirlandi.\n")

    p("=" * 60)
    p("OEM Parts Online - Air Bag System Scraper")
    p(f"Tarih  : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    p(f"Marka  : {', '.join(brands)}")
    p(f"Cikti  : {os.path.abspath(OUTPUT_DIR)}/")
    p("=" * 60)

    scraper = new_scraper()
    total_parts = 0

    for i, brand in enumerate(brands, 1):
        p(f"\n[{i}/{len(brands)}] {brand}")
        p("-" * 40)
        count, scraper = scrape_brand(scraper, brand, reset)
        total_parts += count
        if i < len(brands):
            time.sleep(REQUEST_DELAY)

    p("\n" + "=" * 60)
    p("TAMAMLANDI!")
    p(f"Toplam parca : {total_parts}")
    p(f"JSON dosyalar: {os.path.abspath(OUTPUT_DIR)}/")
    for b in brands:
        path = os.path.join(OUTPUT_DIR, brand_filename(b))
        if os.path.exists(path):
            data = load_brand_data(b)
            p(f"  {brand_filename(b):25s} -> {len(data)} parca")
    p("=" * 60)


if __name__ == '__main__':
    main()
