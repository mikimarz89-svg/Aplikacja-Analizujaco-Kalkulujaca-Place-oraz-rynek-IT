import json
import statistics
from pathlib import Path

def get_offer_salary(offer: dict) -> float | None:
    """Oblicza uśrednione wynagrodzenie miesięczne dla pojedynczej oferty na podstawie widełek."""
    s_min = offer.get("salary_min")
    s_max = offer.get("salary_max")
    
    try:
        if s_min and s_max:
            return (int(s_min) + int(s_max)) / 2.0
        elif s_min:
            return float(s_min)
        elif s_max:
            return float(s_max)
    except (ValueError, TypeError):
        pass
    
    return None

def calculate_stats(data: list, selected_tags: set, logic: str = "AND") -> None:
    """Filtruje dane i oblicza/wyświetla statystyki w konsoli."""
    if not selected_tags:
        print("\n[!] Brak wybranych tagów. Dodaj tagi przed obliczeniami.")
        return

    matching_salaries = []
    
    for offer in data:
        # Zabezpieczenie przed brakiem tagów w ofercie
        offer_tags = set(offer.get("tags") or [])
        
        # Konwersja na małe litery, aby szukanie było case-insensitive
        offer_tags_lower = {t.lower() for t in offer_tags}
        selected_tags_lower = {t.lower() for t in selected_tags}
        
        match = False
        if logic == "AND":
            # Oferta musi zawierać WSZYSTKIE wybrane tagi
            match = selected_tags_lower.issubset(offer_tags_lower)
        elif logic == "OR":
            # Oferta musi zawierać PRZYNAJMNIEJ JEDEN z wybranych tagów
            match = not selected_tags_lower.isdisjoint(offer_tags_lower)
        
        if match:
            salary = get_offer_salary(offer)
            if salary is not None:
                matching_salaries.append(salary)
    
    print(f"\n--- Wyniki dla tagów: {list(selected_tags)} (Logika: {logic}) ---")
    
    if not matching_salaries:
        print("Brak ofert z podanym wynagrodzeniem dla tych kryteriów.")
        print("-" * 60)
        return
        
    mean_sal = statistics.mean(matching_salaries)
    median_sal = statistics.median(matching_salaries)
    min_sal = min(matching_salaries)
    max_sal = max(matching_salaries)
    
    print(f"Liczba uwzględnionych ofert : {len(matching_salaries)}")
    print(f"Średnia arytmetyczna       : {mean_sal:.2f} PLN")
    print(f"Mediana                    : {median_sal:.2f} PLN")
    print(f"Najmniejsze wynagrodzenie  : {min_sal:.2f} PLN")
    print(f"Największe wynagrodzenie   : {max_sal:.2f} PLN")
    print("-" * 60)

def main():
    file_path = Path("data.json")
    if not file_path.exists():
        print(f"Nie znaleziono pliku {file_path}. Odpal najpierw scraper.")
        return

    with file_path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    selected_tags = set()
    logic = "AND"

    print("=== Interaktywny Kalkulator Wynagrodzeń ===")
    
    while True:
        print(f"\nObecnie wybrane tagi: {list(selected_tags) if selected_tags else 'Brak'}")
        print(f"Obecna logika: {logic} ('AND' - musi mieć wszystkie, 'OR' - wystarczy jeden)")
        print("\nDostępne akcje:")
        print("  [1] Dodaj tag")
        print("  [2] Usuń tag")
        print("  [3] Zmień logikę (AND <-> OR)")
        print("  [4] Oblicz statystyki")
        print("  [5] Wyjście")
        
        choice = input("Wybierz akcję (1-5): ").strip()
        
        if choice == '1':
            new_tag = input("Wpisz tag do dodania: ").strip()
            if new_tag:
                selected_tags.add(new_tag)
                print(f"[+] Dodano tag: {new_tag}")
        
        elif choice == '2':
            old_tag = input("Wpisz tag do usunięcia: ").strip()
            # Używamy konwersji na małe litery, żeby było łatwiej usuwać (np. wpisanie 'python' usunie 'Python')
            tag_to_remove = next((t for t in selected_tags if t.lower() == old_tag.lower()), None)
            
            if tag_to_remove:
                selected_tags.remove(tag_to_remove)
                print(f"[-] Usunięto tag: {tag_to_remove}")
            else:
                print(f"[!] Nie znaleziono tagu '{old_tag}' na liście.")
                
        elif choice == '3':
            logic = "OR" if logic == "AND" else "AND"
            print(f"[*] Logika zmieniona na: {logic}")
            
        elif choice == '4':
            calculate_stats(data, selected_tags, logic)
            
        elif choice == '5':
            print("Zamykanie programu...")
            break
            
        else:
            print("[!] Nieprawidłowy wybór. Wpisz cyfrę od 1 do 5.")

if __name__ == "__main__":
    main()