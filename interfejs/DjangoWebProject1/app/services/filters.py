

def filter_offers(offers: list[dict], required_tags=None, excluded_tags=None, mode="AND",
                  work_mode=None, contract_type=None, date_from=None, date_to=None):
    filtered = []
    for offer in offers:
        tags = offer.get("tags", [])

        # Wykluczenia tagów
        if excluded_tags and any(t in tags for t in excluded_tags):
            continue

        # Wymagane tagi
        if required_tags:
            if mode.upper() == "AND":
                if not all(t in tags for t in required_tags):
                    continue
            elif mode.upper() == "OR":
                if not any(t in tags for t in required_tags):
                    continue

        # Tryb pracy
        if work_mode and offer.get("work_mode") != work_mode:
            continue

        # Rodzaj umowy
        if contract_type and offer.get("contract_type") != contract_type:
            continue

        # Zakres dat (data pobrania w formacie YYYY-MM-DD)
        offer_date = offer.get("date")
        if date_from and offer_date < date_from:
            continue
        if date_to and offer_date > date_to:
            continue

        filtered.append(offer)

    return filtered