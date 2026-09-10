import re
from datetime import datetime
from playwright.sync_api import sync_playwright

# ============================================================
# POMOCNICZE
# ============================================================

def clean_text(text: str) -> str:
    if not text:
        return ""
    return re.sub(r'[\s\u00a0\u202f\n\r]+', ' ', text).strip()


# ============================================================
# SALARY
# ============================================================

def extract_salary(raw_text: str) -> tuple[str | None, str | None, str | None]:
    clean_str = clean_text(raw_text)
    normalized_str = re.sub(r'(?<=\d)[\s\xa0\u202f,.]+(?=\d)', '', clean_str)

    pattern = r'(\d{4,6})\s*(?:PLN|EUR|USD|zł|€|\$)?\s*[-–—−]\s*(\d{4,6})'
    match = re.search(pattern, normalized_str, re.IGNORECASE)

    if match:
        min_val, max_val = match.groups()
        try:
            num_min, num_max = int(min_val), int(max_val)
            if 1000 <= num_min <= 250000 and num_max >= num_min:
                currency = "PLN"
                if re.search(r'\b(EUR|€)\b', clean_str, re.IGNORECASE):
                    currency = "EUR"
                elif re.search(r'\b(USD|\$)\b', clean_str, re.IGNORECASE):
                    currency = "USD"
                elif re.search(r'\bPLN\b|\bzł\b', clean_str, re.IGNORECASE):
                    currency = "PLN"
                return (str(num_min), str(num_max), currency)
        except ValueError:
            pass

    return None, None, None


def extract_hourly_rate(text: str) -> tuple[str | None, str | None, str | None]:
    clean_str = clean_text(text)
    normalized_str = re.sub(r'(?<=\d)[\s\xa0\u202f,.]+(?=\d)', '', clean_str)

    pattern = (
        r'(\d{2,4})\s*(?:PLN|EUR|USD|zł|€|\$)?\s*[-–—−]\s*(\d{2,4})\s*'
        r'(PLN|zł|EUR|€|USD|\$)\s*(?:/|\s)?(h|hr|hour|godz|day|dzień)\.?\b'
    )

    match = re.search(pattern, normalized_str, re.IGNORECASE)
    if match:
        min_h, max_h, currency = match.group(1), match.group(2), match.group(3)
        try:
            if int(min_h) >= 10 and int(max_h) >= int(min_h):
                currency_lower = currency.lower()
                if currency_lower in ("zł", "pln"): currency = "PLN"
                elif currency_lower in ("€", "eur"): currency = "EUR"
                elif currency_lower in ("$", "usd"): currency = "USD"
                return (min_h, max_h, currency)
        except ValueError:
            pass

    return None, None, None


# ============================================================
# TAGI (Oczyszczone i restrykcyjne filtrowanie)
# ============================================================

def extract_tags(raw_text: str, title: str) -> list[str]:
    if not raw_text:
        return []

    lines = [line.strip() for line in raw_text.splitlines() if line.strip()]
    tags = []
    
    # Słowa kluczowe i artefakty interfejsu do bezwzględnego odrzucenia
    stop_words = {
        "remote", "hybrid", "office", "on-site", "onsite", 
        "b2b", "uop", "uz", "permanent", "contract", "freelance",
        "full-time", "part-time", "new", "nowość", "undisclosed", "salary",
        "miesięcznie", "month", "monthly", "hour", "hr", "godz", "godz.",
        "junior", "mid", "regular", "senior", "expert", "lead", "manager", "intern",
        "aplikuj", "apply", "live status", "locations", "location", "any"
    }
    
    locations = {
        "warszawa", "kraków", "wrocław", "poznań", "gdańsk", "łódź",
        "katowice", "szczecin", "lublin", "gdynia", "białystok", "bydgoszcz",
        "rzeszów", "gliwice", "kielce", "toruń", "polska", "poland", "krakow"
    }

    for line in lines:
        low = line.lower()
        
        # 1. Odrzucamy tytuł oferty
        if title and low == title.lower(): 
            continue
            
        # 2. Odrzucamy nazwy firm (np. zawierające formy spółek)
        if any(company_suffix in low for company_suffix in ["sp. z o.o", "s.a.", "spk", "inc.", "corp"]): 
            continue
            
        # 3. Odrzucamy słowa z czarnej listy i miasta
        if low in stop_words or low in locations: 
            continue
            
        # 4. Odrzucamy liczniki typu "+4", "+9", same przecinki lub kropki
        if re.fullmatch(r'[\+\d\s,\•\-]+', line): 
            continue
            
        # 5. BEZWZGLĘDNIE odrzucamy linie zawierające cyfry lub słowa powiązane z finansami/czasem
        if re.search(r'\d', low): 
            continue
        if re.search(r'\b(pln|eur|usd|zł|\$|€|k|/h|left|dni|temu|month|day)\b', low): 
            continue
            
        # 6. Tagi to zazwyczaj zwięzłe słowa (max 3 słowa, max 25 znaków)
        if len(line) > 25 or len(line.split()) > 3: 
            continue

        # 7. Unikalność
        if line not in tags:
            tags.append(line)

    # Zwracamy sensowne tagi z końcowej partii tekstu karty
    return tags[-8:] if len(tags) > 8 else tags


# ============================================================
# METADANE
# ============================================================

def extract_work_mode(raw_text: str) -> str | None:
    text = raw_text.lower()
    if re.search(r'\bremote\b', text): return "Remote"
    if re.search(r'\bhybrid\b', text): return "Hybrid"
    if re.search(r'\boffice\b|\bon-site\b|\bonsite\b', text): return "Office"
    return None

def extract_contract_type(raw_text: str) -> str | None:
    if re.search(r'\bB2B\b', raw_text, re.IGNORECASE): return "B2B"
    if re.search(r'\bUoP\b|Umowa o pracę', raw_text, re.IGNORECASE): return "UoP"
    if re.search(r'\bUZ\b|Umowa zlecenie', raw_text, re.IGNORECASE): return "UZ"
    return None


# ============================================================
# OFFER DATA
# ============================================================

def extract_offer_data(card_link) -> dict | None:
    try:
        data = card_link.evaluate("""el => {
            const parent = el.parentElement;
            if (!parent) return null;
            
            const heading = parent.querySelector('h2, h3, h4, [class*="title"], [data-testid="offer-title"]');
            
            return {
                rawText: parent.innerText,
                title: heading ? heading.innerText : '',
                href: el.href
            };
        }""")
    except Exception:
        return None

    if not data or not data.get("rawText"):
        return None

    raw_text = data["rawText"]
    title = clean_text(data["title"])
    title = re.sub(r'\d+\s*d\s*left', '', title, flags=re.IGNORECASE).strip()

    if not title or len(title) < 2:
        lines = [clean_text(line) for line in raw_text.splitlines() if clean_text(line)]
        for line in lines:
            if re.search(r'\d+\s*d\s*left|Undisclosed|PLN|EUR|zł|month|hybrid|remote|•', line, re.IGNORECASE):
                continue
            if len(line.split()) >= 2:
                title = line
                break

    salary_min, salary_max, currency = extract_salary(raw_text)
    hourly_min, hourly_max, hourly_currency = extract_hourly_rate(raw_text)
    tags = extract_tags(raw_text, title)

    href = data["href"]
    if href and href.startswith("/"):
        href = "https://justjoin.it" + href

    return {
        "title": title,
        "tags": tags,
        "salary_min": salary_min,
        "salary_max": salary_max,
        "currency": currency,
        "hourly_min": hourly_min,
        "hourly_max": hourly_max,
        "hourly_currency": hourly_currency,
        "work_mode": extract_work_mode(raw_text),
        "contract_type": extract_contract_type(raw_text),
        "url": href,
        "date": datetime.now().strftime("%Y-%m-%d"),
    }


# ============================================================
# COOKIES
# ============================================================

def dismiss_cookies(page) -> None:
    cookie_selectors = [
        '#qc-cmp2-ui button[mode="primary"]',
        'button:has-text("Akceptuję")',
        'button:has-text("Zgadzam się")',
        'button:has-text("Wszystkie")',
        'button:has-text("Accept")'
    ]
    for selector in cookie_selectors:
        try:
            btn = page.query_selector(selector)
            if btn and btn.is_visible():
                btn.click()
                print("✅ Zamknięto okno zgody na cookies.")
                page.wait_for_timeout(1000)
                return
        except Exception:
            pass


# ============================================================
# FETCH OFFERS (Z obsługą Ctrl + C)
# ============================================================

def fetch_offers(limit: int = 0) -> list[dict]:
    offers = []
    seen_hrefs = set()

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, args=["--start-maximized"])
        context = browser.new_context(
            viewport={"width": 1920, "height": 1080},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36"
        )
        page = context.new_page()

        print("Ładowanie strony...")
        page.goto("https://justjoin.it", timeout=60000, wait_until="domcontentloaded")
        page.wait_for_timeout(3000)

        dismiss_cookies(page)
        print("Rozpoczynam przewijanie i parsowanie ofert... (Wciśnij Ctrl+C, aby zatrzymać)")

        stable, prev_count = 0, 0

        try:
            for i in range(100):
                page.evaluate("window.scrollBy(0, 600)")
                page.wait_for_timeout(100)

                card_links = page.query_selector_all('a.offer-card')

                for card_link in card_links:
                    try:
                        data = extract_offer_data(card_link)
                        if not data or not data["url"]: continue
                        
                        if data["url"] in seen_hrefs: continue
                        seen_hrefs.add(data["url"])
                        offers.append(data)

                        idx = len(offers)

                        if data.get("currency"):
                            salary_str = f"{data['salary_min']}-{data['salary_max']} {data['currency']}"
                        elif data.get("hourly_currency"):
                            salary_str = f"{data['hourly_min']}-{data['hourly_max']} {data['hourly_currency']}/h"
                        else:
                            salary_str = "brak widełek"

                        tags_display = ", ".join(data["tags"])
                        
                        print(f"[{idx}] {data['title'][:35].ljust(35)} | {salary_str.ljust(20)} | Tagi: {tags_display}")

                        if limit > 0 and len(offers) >= limit:
                            break
                    except Exception:
                        continue

                if limit > 0 and len(offers) >= limit:
                    print(f"Osiągnięto limit {limit} ofert.")
                    break

                if len(offers) == prev_count:
                    stable += 1
                    if stable >= 10:
                        print("Brak nowych ofert. Kończę pobieranie.")
                        break
                else:
                    stable = 0
                    prev_count = len(offers)
                    
        except KeyboardInterrupt:
            print("\n🛑 Zatrzymano pobieranie ręcznie (Ctrl+C)!")
            print("Zamykanie przeglądarki i zapisywanie dotychczasowych wyników...")

        browser.close()

    print(f"Łącznie sparsowano {len(offers)} pełnych ofert.")
    return offers


if __name__ == "__main__":
    fetch_offers(20)