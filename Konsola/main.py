from pathlib import Path
import json
import re
import argparse
import logging
import sys
from datetime import datetime
from shutil import copy2
from typing import Union, Optional, Dict, List
from collections import Counter
import statistics

# Zewnętrzne moduły projektu użytkownika
from update import update_data
from storage import load_data, DATA_FILE
import stats_calculator
import filters  # upewnij się, że masz ten moduł

# konfiguracja logowania
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

# regexy
RANGE_RE = re.compile(r"(\d[\d\s\u00a0]*)\s*[-–—]\s*(\d[\d\s\u00a0]*)")
SINGLE_RE = re.compile(r"(\d[\d\s\u00a0]+)")
UNIT_RE = re.compile(r"(PLN(?:\/month|\/h|\/day|\/year)?|EUR|€|zł)", re.IGNORECASE)
HOUR_UNIT = re.compile(r"\/h", re.IGNORECASE)
MONTH_UNIT = re.compile(r"\/month", re.IGNORECASE)
DAY_UNIT = re.compile(r"\/day", re.IGNORECASE)
YEAR_UNIT = re.compile(r"\/year", re.IGNORECASE)

# dodatkowe regexy używane tylko przy wyświetlaniu/tagach
SIMPLE_RANGE_RE = re.compile(r"^\s*\d[\d\s\u00a0]*\s*[-–—]\s*\d[\d\s\u00a0]*\s*$")
PURE_NUMBER_RE = re.compile(r"^\s*\d[\d\s\u00a0]*\s*$")
UNIT_ONLY_RE = re.compile(r"^(PLN(?:\/month|\/h|\/day|\/year)?|EUR|€|zł)$", re.IGNORECASE)


def clean_number(s: str) -> int:
    if not s:
        raise ValueError("empty")
    s = re.sub(r"[^\d]", "", s)  # usuń spacje, NBSP, przecinki itp.
    return int(s)


def detect_unit(tags_join: str) -> Optional[str]:
    m = UNIT_RE.search(tags_join)
    return m.group(1) if m else None


def normalize_offer(o: dict) -> dict:
    tags = o.get("tags") or []
    tags_join = " ".join(tags)
    
    # nie nadpisuj istniejących wartości jeśli już ustawione
    salary_min = o.get("salary_min")
    salary_max = o.get("salary_max")
    currency = o.get("currency")
    hourly_min = o.get("hourly_min")
    hourly_max = o.get("hourly_max")
    hourly_currency = o.get("hourly_currency")

    # jeśli w tags istnieje jawny range
    range_match = RANGE_RE.search(tags_join)
    unit = detect_unit(tags_join)

    try:
        if range_match and unit:
            a = clean_number(range_match.group(1))
            b = clean_number(range_match.group(2))
            # rozróżnij czy to stawka godzinowa czy miesięczna/dzienna/roczna
            if HOUR_UNIT.search(unit):
                if not hourly_min:
                    o["hourly_min"] = str(a)
                if not hourly_max:
                    o["hourly_max"] = str(b)
                if not hourly_currency:
                    o["hourly_currency"] = "PLN" if "PLN" in unit.upper() else unit
            else:
                if not salary_min:
                    o["salary_min"] = str(a)
                if not salary_max:
                    o["salary_max"] = str(b)
                if not currency:
                    o["currency"] = "PLN" if "PLN" in unit.upper() else unit
            return o
    except (ValueError, TypeError) as ex:
        logging.exception("Błąd parsowania zakresu w tagach: %s", tags_join)

    # pojedyncza wartość obok jednostki (np. "33 600 PLN/month" albo ["33 600","PLN/month"])
    single_match = SINGLE_RE.search(tags_join)
    if single_match and unit:
        try:
            v = clean_number(single_match.group(1))
            if HOUR_UNIT.search(unit):
                if not hourly_min:
                    o["hourly_min"] = str(v)
                if not hourly_max:
                    o["hourly_max"] = str(v)
                if not hourly_currency:
                    o["hourly_currency"] = "PLN" if "PLN" in unit.upper() else unit
            else:
                if not salary_min:
                    o["salary_min"] = str(v)
                if not salary_max:
                    o["salary_max"] = str(v)
                if not currency:
                    o["currency"] = "PLN" if "PLN" in unit.upper() else unit
            return o
        except (ValueError, TypeError) as ex:
            logging.exception("Błąd parsowania pojedynczej wartości w tagach: %s", tags_join)

    # jeśli brakuje jednostki, próbuj zidentyfikować parę (liczba + osobny tag jednostki)
    for i, t in enumerate(tags):
        try:
            if m2 := RANGE_RE.match(t):
                a = clean_number(m2.group(1))
                b = clean_number(m2.group(2))
                # sprawdź sąsiednie tagi na jednostkę
                neigh = " ".join(tags[max(0, i - 1): min(len(tags), i + 2)])
                unit2 = detect_unit(neigh) or detect_unit(tags_join)
                if unit2 and HOUR_UNIT.search(unit2):
                    if not hourly_min:
                        o["hourly_min"] = str(a)
                    if not hourly_max:
                        o["hourly_max"] = str(b)
                    if not hourly_currency:
                        o["hourly_currency"] = "PLN"
                else:
                    if not salary_min:
                        o["salary_min"] = str(a)
                    if not salary_max:
                        o["salary_max"] = str(b)
                    if not currency:
                        o["currency"] = "PLN"
                return o
            if SINGLE_RE.fullmatch(t) or SINGLE_RE.match(t):
                v = clean_number(t)
                neigh = " ".join(tags[max(0, i - 1): min(len(tags), i + 2)])
                unit2 = detect_unit(neigh) or detect_unit(tags_join)
                if unit2 and HOUR_UNIT.search(unit2):
                    if not hourly_min:
                        o["hourly_min"] = str(v)
                    if not hourly_max:
                        o["hourly_max"] = str(v)
                    if not hourly_currency:
                        o["hourly_currency"] = "PLN"
                else:
                    if not salary_min:
                        o["salary_min"] = str(v)
                    if not salary_max:
                        o["salary_max"] = str(v)
                    if not currency:
                        o["currency"] = "PLN"
                return o
        except (ValueError, TypeError):
            logging.exception("Błąd parsowania tagu na pozycji %d: %s", i, t)
            continue

    return o


def normalize_file(file_path: Union[str, Path]) -> Dict[str, Union[str, int]]:
    """
    Normalizuje zawartość pliku JSON z ofertami.
    Usuwa duplikaty opierając się na stabilnej sygnaturze.
    """
    file_path = Path(file_path)
    if not file_path.exists():
        raise FileNotFoundError(f"Brak pliku: {file_path}")

    # backup obok pliku (dodajemy .bak do sufiksu)
    if file_path.suffix:
        backup_path = file_path.with_suffix(file_path.suffix + ".bak")
    else:
        backup_path = file_path.with_name(file_path.name + ".bak")

    copy2(file_path, backup_path)

    with file_path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    changed = 0
    unique_data: List[dict] = []
    seen_signatures = set()
    duplicates_removed = 0

    for i, offer in enumerate(data):
        before = json.dumps(offer, sort_keys=True)
        norm_offer = normalize_offer(offer)

        # stabilna sygnatura — bez tagów, bo są niestabilne
        signature = (
            norm_offer.get("title", "").strip().lower(),
            norm_offer.get("salary_min"),
            norm_offer.get("salary_max"),
            norm_offer.get("work_mode"),
            norm_offer.get("contract_type"),
        )

        if signature in seen_signatures:
            duplicates_removed += 1
            changed += 1  # usunięcie duplikatu to również zmiana
            continue

        seen_signatures.add(signature)
        unique_data.append(norm_offer)

        after = json.dumps(norm_offer, sort_keys=True)
        if before != after:
            changed += 1

    # Zapisz unikalne i znormalizowane dane
    out_path = file_path
    with out_path.open("w", encoding="utf-8") as f:
        json.dump(unique_data, f, ensure_ascii=False, indent=2)

    meta = {
        "file": str(file_path),
        "backup": str(backup_path),
        "normalized_count": changed,
        "duplicates_removed": duplicates_removed,
        "updated_at": datetime.now().isoformat(),
    }
    return meta


def _is_displayable_tag(t: Optional[str]) -> bool:
    """
    Zwraca True jeśli tag powinien być wyświetlany w menu.
    """
    if t is None:
        return False
    s = str(t).strip()
    if not s:
        return False
    if len(s) > 80:
        return False
    if SIMPLE_RANGE_RE.match(s):
        return False
    if PURE_NUMBER_RE.match(s):
        return False
    if UNIT_ONLY_RE.match(s):
        return False
    return True


def _offer_monthly_salary(offer: dict) -> Optional[float]:
    """
    Zwraca średnie miesięczne wynagrodzenie z pola salary_min/salary_max (PLN) lub None.
    Nie bierze pod uwagę stawek godzinowych (hourly_*).
    """
    s_min = offer.get("salary_min")
    s_max = offer.get("salary_max")
    try:
        if s_min and s_max:
            return (int(s_min) + int(s_max)) / 2.0
        if s_min:
            return float(s_min)
        if s_max:
            return float(s_max)
    except (ValueError, TypeError):
        return None
    return None


def collect_tags_from_file(file_path: Union[str, Path]) -> Counter:
    """Zwraca Counter wszystkich tagów znalezionych w pliku JSON."""
    p = Path(file_path)
    if not p.exists():
        raise FileNotFoundError(f"Brak pliku: {p}")
    with p.open("r", encoding="utf-8") as f:
        data = json.load(f)
    cnt = Counter()
    for item in data:
        tags = item.get("tags") or []
        for t in tags:
            if t is None:
                continue
            ts = str(t).strip()
            if not _is_displayable_tag(ts):
                continue
            cnt[ts] += 1
    return cnt


def collect_tag_stats_from_file(file_path: Union[str, Path]) -> Dict[str, Dict]:
    """Zwraca mapę tag -> {'count': int, 'salaries': List[float]}"""
    p = Path(file_path)
    if not p.exists():
        raise FileNotFoundError(f"Brak pliku: {p}")
    with p.open("r", encoding="utf-8") as f:
        data = json.load(f)

    tag_map: Dict[str, Dict] = {}
    for item in data:
        tags = item.get("tags") or []
        salary = _offer_monthly_salary(item)
        for t in tags:
            if t is None:
                continue
            ts = str(t).strip()
            if not _is_displayable_tag(ts):
                continue
            entry = tag_map.setdefault(ts, {"count": 0, "salaries": []})
            entry["count"] += 1
            if salary is not None:
                entry["salaries"].append(salary)
    return tag_map


def print_tags_from_file(file_path: Union[str, Path], top: Optional[int] = None, sort_by: str = "count"):
    try:
        cnt = collect_tags_from_file(file_path)
        tag_stats = collect_tag_stats_from_file(file_path)
    except FileNotFoundError as ex:
        logging.error(ex)
        return
        
    total_unique = len(cnt)
    total_occurrences = sum(cnt.values())
    print(f"Plik: {file_path}")
    print(f"Unikalnych tagów: {total_unique}, łącznie wystąpień: {total_occurrences}")
    
    # Obliczanie statystyk przed sortowaniem
    enriched_items = []
    for tag, count in cnt.items():
        stats = tag_stats.get(tag, {})
        salaries = stats.get("salaries", []) if stats else []
        if salaries:
            try:
                mean_val = statistics.mean(salaries)
                median_val = statistics.median(salaries)
            except statistics.StatisticsError:
                mean_val, median_val = 0.0, 0.0
        else:
            mean_val, median_val = 0.0, 0.0
            
        enriched_items.append({
            "tag": tag,
            "count": count,
            "mean": mean_val,
            "median": median_val,
            "has_salary": bool(salaries)
        })

    # Sortowanie
    if sort_by == "name":
        enriched_items.sort(key=lambda x: x["tag"].lower())
    elif sort_by == "mean":
        enriched_items.sort(key=lambda x: (-x["mean"], -x["count"]))
    elif sort_by == "median":
        enriched_items.sort(key=lambda x: (-x["median"], -x["count"]))
    else:
        # domyślnie: po ilości
        enriched_items.sort(key=lambda x: (-x["count"], x["tag"].lower()))
        
    if top:
        enriched_items = enriched_items[:top]
        
    # Wyświetlanie
    print(f"{'cnt':>4s}  {'tag':40s}  {'mean PLN':>10s}  {'median PLN':>11s}")
    print("-" * 80)
    for item in enriched_items:
        if item["has_salary"]:
            mean_s = f"{item['mean']:.2f}"
            median_s = f"{item['median']:.2f}"
        else:
            mean_s = median_s = "-"
            
        print(f"{item['count']:4d}  {item['tag']:40s}  {mean_s:>10s}  {median_s:>11s}")


def print_summary(data):
    print("\n📊 Podsumowanie:")
    print(f"📦 Liczba ofert: {len(data)}")
    if len(data) > 0:
        print(f"🔎 Przykładowa oferta: {data[0].get('title', 'Brak')}")


def show_tags():
    top = input("Pokaż top N tagów (ENTER = wszystkie): ").strip()
    top_n = int(top) if top.isdigit() else None
    
    print("\nSortuj po:")
    print("1 - Liczbie ofert (domyślnie)")
    print("2 - Nazwie (alfabetycznie)")
    print("3 - Średniej pensji (mean)")
    print("4 - Medialnej pensji (median)")
    sort_choice = input("Wybierz opcję: ").strip()
    
    if sort_choice == "2":
        sort_mode = "name"
    elif sort_choice == "3":
        sort_mode = "mean"
    elif sort_choice == "4":
        sort_mode = "median"
    else:
        sort_mode = "count"
    
    print_tags_from_file(DATA_FILE, top=top_n, sort_by=sort_mode)


def filter_menu(offers):
    print("\n--- Filtrowanie i Sortowanie ---")
    
    # 1. Wybór tagów
    tags_input = input("Wpisz tagi oddzielone przecinkami (ENTER=pomiń): ").strip()
    tags = [t.strip() for t in tags_input.split(',')] if tags_input else []
    
    # 2. Wybór logiki
    mode = "AND"
    if tags:
        choice = input("Wybierz logikę tagów (AND/OR) [ENTER=AND]: ").strip().upper()
        if choice == "OR":
            mode = "OR"

    # 3. Filtry dodatkowe
    work_mode = input("Tryb pracy (Remote/Hybrid/Office) [ENTER=pomiń]: ").strip() or None
    contract_type = input("Rodzaj umowy (B2B/UoP) [ENTER=pomiń]: ").strip() or None

    # 4. Filtrowanie
    filtered = filters.filter_offers(
        offers,
        required_tags=tags,
        mode=mode,
        work_mode=work_mode,
        contract_type=contract_type
    )

    if not filtered:
        print("Brak ofert spełniających kryteria.")
        return

    # 5. Opcje sortowania wyników
    print("\nJak posortować wyniki?")
    print("1. Od najnowszych (po dacie)")
    print("2. Od najwyższej pensji")
    print("3. Od najniższej pensji")
    print("ENTER. Brak sortowania")
    
    sort_choice = input("Wybierz opcję: ").strip()
    
    if sort_choice == "1":
        # Sortowanie po dacie (od najnowszych)
        filtered.sort(key=lambda x: str(x.get('date', x.get('published_at', ''))), reverse=True)
    elif sort_choice == "2":
        # Sortowanie od najwyższej pensji
        filtered.sort(key=lambda x: _offer_monthly_salary(x) or 0, reverse=True)
    elif sort_choice == "3":
        # Sortowanie od najniższej pensji
        filtered.sort(key=lambda x: _offer_monthly_salary(x) or float('inf'))

    print(f"\nZnaleziono {len(filtered)} ofert pasujących do kryteriów.")

    # 6. Wyświetlanie wyników
    show = input("Czy wyświetlić listę ofert? [t/n]: ").lower()
    if show == 't':
        for o in filtered:
            date_str = o.get('date', o.get('published_at', 'Brak daty'))
            title = o.get('title', 'Brak tytułu')
            s_min = o.get('salary_min') or '?'
            s_max = o.get('salary_max') or '?'
            currency = o.get('currency', 'PLN')
            
            print(f"- [{date_str}] {title} | {s_min}-{s_max} {currency}")
        
    # 7. Automatyczna kalkulacja statystyk dla przefiltrowanych danych
    print("\nObliczam statystyki...")
    stats_calculator.calculate_stats(filtered, set(tags), logic=mode)


def main():
    offers = load_data()
    while True:
        print("\n===== MENU =====")
        print("1. Aktualizuj dane")
        print("2. Wyświetl tagi")
        print("3. Kalkulator statystyk")
        print("4. Filtruj i pokaż statystyki")
        print("5. Wyjście")
        
        choice = input("Wybierz opcję: ").strip()

        if choice == "1":
            print("🔄 Aktualizacja danych...")
            update_data()
            offers = load_data()
            print_summary(offers)
        elif choice == "2":
            show_tags()
        elif choice == "3":
            stats_calculator.main()
        elif choice == "4":
            filter_menu(offers)
        elif choice == "5":
            break
        else:
            print("Nieznana opcja.")


if __name__ == "__main__":
    main()