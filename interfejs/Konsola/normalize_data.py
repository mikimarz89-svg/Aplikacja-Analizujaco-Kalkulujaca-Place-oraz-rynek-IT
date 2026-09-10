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

    # pojedyncza wartość obok jednostki (np. "33 600 PLN/month" albo ["33 600","PLN/month"])
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
            if RANGE_RE.match(t):
                m2 = RANGE_RE.match(t)
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
        except (ValueError, TypeError) as ex:
            logging.exception("Błąd parsowania tagu na pozycji %d: %s", i, t)
            continue

    return o


def normalize_file(file_path: Union[str, Path]) -> Dict[str, Union[str, int]]:
    """
    Normalizuje zawartość pliku JSON z ofertami.
    Usuwa duplikaty opierając się na stabilnej sygnaturze:
      (title.lower().strip(), salary_min, salary_max, work_mode, contract_type)
    Zwraca słownik z metadanymi: {'file', 'backup', 'normalized_count', 'duplicates_removed', 'updated_at'}
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
    Zwraca True jeśli tag powinien być wyświetlany w --list-tags.
    - ukrywa proste przedziały (np. '140 - 190'), czyste liczby i tagi będące tylko jednostką (np. 'PLN/month').
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


def collect_tags_from_file(file_path: Union[str, Path]) -> Counter:
    """
    Zwraca Counter wszystkich tagów znalezionych w pliku JSON.
    Filtruje przedziały liczbowe i tagi-składające-się-tylko-z-liczb/jednostek,
    żeby nie pokazywać widełek jako tagów.
    """
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
            cnt[str(t).strip()] += 1
    return cnt


def print_tags_from_file(file_path: Union[str, Path], top: Optional[int] = None):
    try:
        cnt = collect_tags_from_file(file_path)
    except FileNotFoundError as ex:
        logging.error(ex)
        return
    total_unique = len(cnt)
    total_occurrences = sum(cnt.values())
    print(f"Plik: {file_path}")
    print(f"Unikalnych tagów: {total_unique}, łącznie wystąpień: {total_occurrences}")
    # posortuj według częstości malejąco, potem alfabetycznie
    items = sorted(cnt.items(), key=lambda x: (-x[1], x[0]))
    if top:
        items = items[:top]
    for tag, count in items:
        print(f"{count:4d}  {tag}")


def parse_tags_input(s: str) -> List[str]:
    """
    Parsuje input tagów:
     - JSON array (np. '["33 600","PLN/month"]')
     - przecinki lub średniki rozdzielające
     - whitespace-separated
    Zwraca listę stringów (tagów).
    """
    s = s.strip()
    if not s:
        return []
    try:
        parsed = json.loads(s)
        if isinstance(parsed, list):
            return [str(x) for x in parsed]
    except json.JSONDecodeError:
        pass
    if "," in s or ";" in s:
        parts = re.split(r"[;,]\s*", s)
    else:
        parts = s.split()
    return [p for p in (p.strip() for p in parts) if p]


def normalize_tags_cli(tags_input: str) -> dict:
    tags = parse_tags_input(tags_input)
    offer = {"tags": tags}
    return normalize_offer(offer)


def build_argparser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="normalize_data",
        description="Narzędzie do normalizacji ofert i operacji na tagach.",
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--tags",
        "-t",
        nargs="?",
        const="",
        help="Przetwórz pojedynczą listę tagów (JSON-array lub ciąg). Bez wartości: otwiera prompt.",
    )
    group.add_argument(
        "--list-tags",
        "-l",
        nargs="?",
        const="",
        help="Wypisz unikalne tagi z pliku. Można podać opcjonalną ścieżkę.",
    )
    parser.add_argument("--top", "-T", type=int, default=None, help="Pokaż top N tagów (dla --list-tags).")
    parser.add_argument("path", nargs="?", help="Ścieżka do pliku data.json do normalizacji.")
    return parser


def main(path: Optional[str] = None):
    parser = build_argparser()
    args = parser.parse_args()

    # tryb --tags
    if args.tags is not None:
        tags_arg = args.tags
        if tags_arg == "":
            try:
                tags_arg = input("Wpisz listę tagów (JSON-array lub przecinki/whitespace): ").strip()
            except EOFError:
                logging.error("Brak inputu tagów.")
                return
        result = normalize_tags_cli(tags_arg)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return

    # tryb --list-tags
    if args.list_tags is not None:
        arg_path = args.list_tags or args.path
        candidates = []
        if arg_path:
            candidates.append(Path(arg_path))
        else:
            candidates.append(Path.cwd() / "data.json")
            candidates.append(Path(__file__).parent / "data.json")
        chosen = None
        for p in candidates:
            if p.exists():
                chosen = p
                break
        if not chosen:
            logging.error("Brak pliku data.json w oczekiwanych lokalizacjach: %s", candidates)
            return
        print_tags_from_file(chosen, top=args.top)
        return

    # tryb normalizacji pliku
    candidates = []
    if path:
        candidates.append(Path(path))
    else:
        candidates.append(Path.cwd() / "data.json")
        candidates.append(Path(__file__).parent / "data.json")

    chosen = None
    for p in candidates:
        if p.exists():
            chosen = p
            break

    if not chosen:
        logging.error("Brak pliku data.json w oczekiwanych lokalizacjach: %s", candidates)
        return

    try:
        logging.info("Używam pliku: %s", chosen)
        meta = normalize_file(chosen)
        logging.info("Utworzono backup: %s", meta["backup"])
        logging.info("Zapisano %s — zmienionych rekordów: %d (w tym %d usuniętych duplikatów)",
                     meta["file"], meta["normalized_count"], meta.get("duplicates_removed", 0))
    except (OSError, json.JSONDecodeError) as ex:
        logging.exception("Błąd podczas normalizacji pliku: %s", chosen)
        print(f"Błąd podczas normalizacji: {ex}")


if __name__ == "__main__":
    # jeśli pierwszy argument jest ścieżką, main obsłuży to przez argparse
    main()