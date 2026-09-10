"""
analytics.py – statystyki i top tagi.
"""

def filter_offers_with_salary(offers: list[dict]) -> list[dict]:
    return [o for o in offers if o["salary_min"] is not None and o["salary_max"] is not None]


def calculate_stats(offers: list[dict]):
    with_salary = filter_offers_with_salary(offers)
    if not with_salary:
        return None

    min_vals = [int(o["salary_min"]) for o in with_salary]
    max_vals = [int(o["salary_max"]) for o in with_salary]
    avg_ranges = [(mn + mx) / 2 for mn, mx in zip(min_vals, max_vals)]

    def median(lst):
        n = len(lst)
        s = sorted(lst)
        if n % 2 == 1:
            return s[n // 2]
        else:
            return (s[n // 2 - 1] + s[n // 2]) / 2

    return {
        "count": len(with_salary),
        "avg_min": sum(min_vals) / len(min_vals),
        "avg_max": sum(max_vals) / len(max_vals),
        "avg_range_mid": sum(avg_ranges) / len(avg_ranges),
        "median_min": median(min_vals),
        "median_max": median(max_vals),
        "min_overall": min(min_vals),
        "max_overall": max(max_vals),
    }

def show_sorted_by_date(offers):
    """Sortuje oferty od najnowszej do najstarszej i wyœwietla w konsoli."""
    if not offers:
        print("Brak danych do wyœwietlenia.")
        return

    # Sortowanie: reverse=True oznacza od najnowszej do najstarszej
    sorted_offers = sorted(offers, key=lambda x: x.get('date', '0000-00-00'), reverse=True)

    print(f"\n{'DATA':<12} | {'TYTU£':<40} | {'WIDE£KI'}")
    print("-" * 75)
    
    for o in sorted_offers:
        date = o.get('date') or "Brak daty"
        title = (o.get('title') or "Brak tytu³u")[:38]
        
        # Przygotowanie czytelnych wide³ek
        s_min = o.get('salary_min') or "?"
        s_max = o.get('salary_max') or "?"
        salary = f"{s_min}-{s_max}"
        
        print(f"{date:<12} | {title:<40} | {salary:<10}")

    print("-" * 75)
def top_tags(offers: list[dict], sort_by="frequency", top_n=10):
    """
    Zwraca listê krotek (tag, liczba_wyst¹pieñ, œredni_œrodek_wide³ek).
    sort_by: 'frequency', 'avg_salary', 'median_salary'
    """
    tag_stats = {}
    for offer in offers:
        for tag in offer.get("tags", []):
            if tag not in tag_stats:
                tag_stats[tag] = {"count": 0, "salaries": []}
            tag_stats[tag]["count"] += 1
            if offer["salary_min"] and offer["salary_max"]:
                tag_stats[tag]["salaries"].append((int(offer["salary_min"]) + int(offer["salary_max"])) / 2)

    result = []
    for tag, data in tag_stats.items():
        avg_sal = sum(data["salaries"]) / len(data["salaries"]) if data["salaries"] else 0
        median_sal = sorted(data["salaries"])[len(data["salaries"]) // 2] if data["salaries"] else 0
        result.append((tag, data["count"], avg_sal, median_sal))

    if sort_by == "frequency":
        result.sort(key=lambda x: x[1], reverse=True)
    elif sort_by == "avg_salary":
        result.sort(key=lambda x: x[2], reverse=True)
    elif sort_by == "median_salary":
        result.sort(key=lambda x: x[3], reverse=True)

    return result[:top_n]