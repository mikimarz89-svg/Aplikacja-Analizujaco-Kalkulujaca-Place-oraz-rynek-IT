import json
import os
from typing import List, Dict, Tuple

DATA_FILE = "data.json"


def load_data() -> List[Dict]:
    if not os.path.exists(DATA_FILE):
        return []
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        content = f.read().strip()
        if not content:          # file exists but is empty
            return []
        return json.loads(content)


def save_data(data: List[Dict]) -> None:
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _offer_key(o: Dict) -> Tuple:
    """
    Generuje klucz używany do wykrywania duplikatów.
    Porównuje znormalizowany tytuł, datę i uporządkowaną listę tagów.
    Dzięki temu nie dodamy tej samej oferty wielokrotnie.
    """
    title = (o.get("title") or "").strip().casefold()
    date = o.get("date") or ""
    tags = tuple(sorted([str(t).strip().casefold() for t in (o.get("tags") or [])]))
    return title, date, tags


def append_data(new_offers: List[Dict]) -> int:
    """
    Dokłada nowe oferty do pliku `data.json`, pomijając duplikaty.
    Zwraca liczbę dodanych ofert.
    """
    data = load_data()
    existing_keys = { _offer_key(x) for x in data }

    appended = 0
    for offer in new_offers:
        key = _offer_key(offer)
        if key in existing_keys:
            continue
        data.append(offer)
        existing_keys.add(key)
        appended += 1

    save_data(data)
    return appended