"""
scraper.py – finalna wersja z ekstrakcją tagów, trybu pracy,
rodzaju umowy oraz stawki godzinowej.
"""

import re
from datetime import datetime
from playwright.sync_api import sync_playwright

# Widełki miesięczne
SALARY_RE = re.compile(
    r"(\d[\d\s\u00a0]{2,})\s*[-\u2013]\s*(\d[\d\s\u00a0]{2,})\s*(PLN|zł|EUR|€)(?!\/h)",
    re.IGNORECASE,
)

# Stawka godzinowa
HOURLY_RE = re.compile(
    r"(\d[\d\s\u00a0]{1,})\s*[-\u2013]\s*(\d[\d\s\u00a0]{1,})\s*(PLN|zł|EUR|€)\s*\/\s*h",
    re.IGNORECASE,
)


def extract_salary(text: str) -> tuple[str | None, str | None, str | None]:
    """Zwraca (min, max, currency) dla miesięcznych widełek."""
    match = SALARY_RE.search(text)
    if not match:
        return None, None, None

    def clean(s: str) -> str:
        return re.sub(r"[\s\u00a0\n]", "", s)

    min_s = clean(match.group(1))
    max_s = clean(match.group(2))
    currency = match.group(3)
    try:
        if int(min_s) >= 1000 and int(max_s) >= 1000:
            return min_s, max_s, currency
    except ValueError:
        pass
    return None, None, None


def extract_hourly_rate(text: str) -> tuple[str | None, str | None, str | None]:
    """Zwraca (min, max, currency) dla stawki godzinowej."""
    match = HOURLY_RE.search(text)
    if not match:
        return None, None, None

    def clean(s: str) -> str:
        return re.sub(r"[\s\u00a0\n]", "", s)

    min_h = clean(match.group(1))
    max_h = clean(match.group(2))
    currency = match.group(3)
    try:
        if int(min_h) >= 20 and int(max_h) >= 20:
            return min_h, max_h, currency
    except ValueError:
        pass
    return None, None, None


def dismiss_cookies(page) -> None:
    try:
        page.click('#qc-cmp2-ui button[mode="primary"]', timeout=3000)
    except Exception:
        pass


def extract_title(card) -> str:
    for selector in [
        '[data-testid="offer-title"]',
        'h2',
        'h3',
        '[class*="title"]',
        '[class*="job-title"]',
    ]:
        el = card.query_selector(selector)
        if el:
            return el.inner_text().strip()

    text = card.inner_text()
    text = re.sub(r'\s+', ' ', text)
    parts = [p.strip() for p in text.split('|') if p.strip()]
    for i in range(len(parts) - 1, 0, -1):
        part = parts[i]
        if re.search(r'\d+d\s*left|Undisclosed', part):
            continue
        if SALARY_RE.search(part):
            continue
        if part.lower() in ('remote', 'office', 'hybrid'):
            continue
        if len(part.split()) >= 2:
            return part
    return "Nieznany tytuł"


def extract_tags(card) -> list[str]:
    tags = set()
    
    # Szukamy tylko konkretnych pigułek (span, div, h6) wewnątrz karty
    # NIE używaj card.inner_text()!
    elements = card.query_selector_all('span, div, h6')
    
    # Słowa, które zawsze są "śmieciami" w tagach
    ignore_list = {
        'remote', 'office', 'hybrid', 'b2b', 'uop', 'uz', 'permanent', 
        'mid', 'senior', 'junior', 'new', 'any', 'internship', 'mandate',
        'contract', 'salary', 'undisclosed'
    }

    for el in elements:
        text = el.inner_text().strip()
        
        # Odrzuć:
        # - Puste teksty
        # - Teksty za długie (to pewnie opisy lub zagnieżdżone kontenery)
        # - Teksty z nową linią (to na 100% zagnieżdżone elementy)
        # - Wzorce dat (np. "30d left")
        if not text or len(text) > 30 or '\n' in text or re.search(r'\d+d left', text, re.I):
            continue

        # Rozdzielanie "sklejonych" tagów (np. SeniorSenior -> Senior)
        # Jeśli długość słowa jest parzysta i lewa połowa jest identyczna z prawą
        if len(text) > 4 and text[:len(text)//2] == text[len(text)//2:]:
            text = text[:len(text)//2]
            
        # Filtrowanie
        text_lower = text.lower()
        if text_lower in ignore_list or any(c.isdigit() for c in text): # Odrzuć jeśli zawiera cyfry (dane pensji)
            continue
            
        tags.add(text)
        
    return list(tags)


def extract_work_mode(card) -> str | None:
    text = card.inner_text().lower()
    for selector in ['span[class*="work-mode"]', 'div[class*="work-mode"]', 'span[class*="location"]']:
        el = card.query_selector(selector)
        if el:
            t = el.inner_text().strip().lower()
            if "remote" in t:
                return "Remote"
            elif "office" in t:
                return "Office"
            elif "hybrid" in t:
                return "Hybrid"
    if re.search(r'\bremote\b', text):
        return "Remote"
    if re.search(r'\bhybrid\b', text):
        return "Hybrid"
    if re.search(r'\boffice\b', text) or re.search(r'\bon-site\b', text):
        return "Office"
    return None


def extract_contract_type(card) -> str | None:
    text = card.inner_text()
    patterns = {
        "B2B": r'\bB2B\b',
        "UoP": r'\bUoP\b|Umowa o pracę',
        "UZ": r'\bUZ\b|Umowa zlecenie',
        "Contract of employment": r'contract of employment',
    }
    for contract, pattern in patterns.items():
        if re.search(pattern, text, re.IGNORECASE):
            return contract
    return None


def load_all_offer_cards(page, limit: int = 0) -> list:
    seen_hrefs = set()
    all_cards = []
    prev_count = 0
    stable = 0

    container = page.query_selector('[data-testid="virtuoso-item-list"]') or \
                page.query_selector('[data-viewport-type]')
    if not container:
        container = page

    print("Rozpoczynam przewijanie listy...")
    for i in range(80):
        if isinstance(container, type(page)):
            page.mouse.wheel(0, 500)
        else:
            container.evaluate("el => el.scrollTop = el.scrollHeight")
        page.wait_for_timeout(800)

        current_cards = page.query_selector_all('a[href^="/job-offer/"]')
        new_cards = [c for c in current_cards if c.get_attribute('href') not in seen_hrefs]
        for c in new_cards:
            seen_hrefs.add(c.get_attribute('href'))
            all_cards.append(c)

        if len(all_cards) == prev_count:
            stable += 1
            if stable >= 5:
                break
        else:
            stable = 0
            prev_count = len(all_cards)

        if limit > 0 and len(all_cards) >= limit:
            print(f"Osiągnięto limit {limit} kart.")
            break

    print(f"Załadowano {len(all_cards)} unikalnych kart ofert.")
    return all_cards[:limit] if limit > 0 else all_cards


def extract_offer_data(card) -> dict:
    text = card.inner_text()
    title = extract_title(card)
    salary_min, salary_max, currency = extract_salary(text)
    hourly_min, hourly_max, hourly_currency = extract_hourly_rate(text)
    tags = extract_tags(card)
    work_mode = extract_work_mode(card)
    contract_type = extract_contract_type(card)

    return {
        "title": title,
        "tags": tags,
        "salary_min": salary_min,
        "salary_max": salary_max,
        "currency": currency,
        "hourly_min": hourly_min,
        "hourly_max": hourly_max,
        "hourly_currency": hourly_currency,
        "work_mode": work_mode,
        "contract_type": contract_type,
        "date": datetime.now().strftime("%Y-%m-%d"),
    }


def fetch_offers(limit: int = 0) -> list[dict]:
    offers = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        print("Ładowanie strony...")
        page.goto("https://justjoin.it", timeout=60000)
        page.wait_for_selector('a[href^="/job-offer/"]', state="attached", timeout=10000)
        dismiss_cookies(page)

        cards = load_all_offer_cards(page, limit)

        print("Parsowanie ofert...")
        for idx, card in enumerate(cards):
            try:
                data = extract_offer_data(card)
                offers.append(data)
                tag_str = ', '.join(data['tags']) if data['tags'] else 'brak tagów'
                salary_str = f"{data['salary_min']}-{data['salary_max']} {data['currency']}" if data['currency'] else "brak widełek"
                hourly_str = f" | {data['hourly_min']}-{data['hourly_max']} {data['hourly_currency']}/h" if data['hourly_currency'] else ""
                print(f"[{idx+1}] {data['title']} | {tag_str} | {salary_str}{hourly_str} | {data['work_mode']} | {data['contract_type']}")
            except Exception as e:
                print(f"Błąd parsowania karty {idx}: {e}")

        browser.close()

    print(f"Łącznie sparsowano {len(offers)} ofert.")
    return offers

if __name__ == "__main__":
    fetch_offers(10) # Testowo pobiera pierwsze 10 ofert