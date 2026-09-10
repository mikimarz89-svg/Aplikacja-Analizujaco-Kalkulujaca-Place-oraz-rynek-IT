import os
import sys
import json
from datetime import datetime

# Pobieranie sciezek
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(CURRENT_DIR)

# Zakladam ze to interfejs/DjangoWebProject1
DJANGO_PROJECT_DIR = os.path.join(ROOT_DIR, 'interfejs', 'DjangoWebProject1')
sys.path.append(DJANGO_PROJECT_DIR)

# Konfiguracja srodowiska
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'DjangoWebProject1.settings')
import django
django.setup()

from app.models import Offer, Tag

def sync_data():
    print("Laczenie z baza Django i przesylanie danych...")
    json_path = os.path.join(CURRENT_DIR, 'data.json')
    
    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            offers_data = json.load(f)
    except FileNotFoundError:
        print("Blad: Nie znaleziono pliku data.json w folderze Konsola!")
        return

    added_count = 0
    for item in offers_data:
        date_str = item.get("date")
        pub_date = None
        if date_str:
            try:
                pub_date = datetime.strptime(date_str, "%Y-%m-%d")
            except ValueError:
                pass

        offer, created = Offer.objects.get_or_create(
            title=item.get("title", "Brak tytulu"),
            salary_min=item.get("salary_min"),
            salary_max=item.get("salary_max"),
            currency=item.get("currency", "PLN") or "PLN",
            work_mode=item.get("work_mode"),
            contract_type=item.get("contract_type"),
            published_at=pub_date
        )

        if created:
            added_count += 1
            for tag_name in item.get("tags", []):
                tag_obj, _ = Tag.objects.get_or_create(name=tag_name)
                offer.tags.add(tag_obj)

    print(f"Sukces! Przeslano {added_count} nowych ofert do bazy Django.")

if __name__ == '__main__':
    sync_data()