from scraper import fetch_offers
from storage import append_data
import normalize_data
import sync_to_django # <-- Dodany import naszego nowego skryptu

def update_data():
    print("Pobieranie ofert...")
    offers = fetch_offers()

    print(f"Pobrano: {len(offers)} ofert")

    append_data(offers)

    print("Zapisano do JSON")

    # Uruchom normalizację (normalize_data robi backup i zapis)
    try:
        print("Uruchamiam normalizację danych (tworzony backup)...")
        normalize_data.main()
        print("Normalizacja zakończona.")
        
        # --- NOWY KROK: Synchronizacja z Django ---
        sync_to_django.sync_data()
        
    except Exception as ex:
        print(f"Błąd podczas normalizacji lub synchronizacji: {ex}")