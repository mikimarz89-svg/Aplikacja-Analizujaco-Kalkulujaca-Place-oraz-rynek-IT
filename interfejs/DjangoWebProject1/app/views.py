from django.shortcuts import render
from django.db.models import Avg, Min, Max
from .models import Offer
import statistics # Potrzebne do obliczenia mediany
import os
from django.conf import settings

def offers_dashboard(request):
    # Domyślnie pobierz wszystkie oferty
    offers = Offer.objects.all()
    
    # Odbieramy parametry z paska adresu (GET)
    tags_input = request.GET.get('tags', '').strip()
    work_mode = request.GET.get('work_mode', '').strip()
    sort_choice = request.GET.get('sort', '').strip()
    logic_mode = request.GET.get('mode', 'OR').strip().upper() # Pobieramy logikę (AND/OR)

    # --- FILTROWANIE ---
    if tags_input:
        tags_list = [t.strip() for t in tags_input.split(',')]
        
        if logic_mode == 'AND':
            # Logika AND: Filtrujemy iteracyjnie, każda oferta MUSI mieć dany tag
            for tag in tags_list:
                offers = offers.filter(tags__name__iexact=tag)
        else:
            # Logika OR: Oferta musi mieć przynajmniej jeden z tagów
            offers = offers.filter(tags__name__in=tags_list).distinct()
        
    if work_mode:
        offers = offers.filter(work_mode__iexact=work_mode)

    # --- SORTOWANIE ---
    if sort_choice == "date":
        offers = offers.order_by('-published_at')
    elif sort_choice == "highest":
        offers = offers.order_by('-salary_max')
    elif sort_choice == "lowest":
        offers = offers.order_by('salary_min')

    # --- STATYSTYKI (MVP nr 5) ---
    stats = None
    if offers.exists() and tags_input:
        # Django może szybko policzyć Średnią, Min i Max na poziomie bazy danych:
        db_stats = offers.aggregate(
            avg_salary=Avg('salary_min'), # Możesz uśredniać z salary_max w zależności od logiki
            min_salary=Min('salary_min'),
            max_salary=Max('salary_max')
        )
        
        # Mediana jest trudniejsza do zrobienia w czystym SQL, więc możemy pobrać zarobki do listy i użyć pythona
        salaries = list(offers.values_list('salary_min', flat=True))
        salaries = [s for s in salaries if s is not None] # Odfiltruj oferty bez podanej pensji
        
        median_salary = statistics.median(salaries) if salaries else 0
        
        stats = {
            'mean': round(db_stats['avg_salary'] or 0, 2),
            'min': db_stats['min_salary'] or 0,
            'max': db_stats['max_salary'] or 0,
            'median': median_salary,
        }

    context = {
        'offers': offers,
        'count': offers.count(),
        'search_tags': tags_input,
        'current_sort': sort_choice,
        'current_mode': logic_mode,
        'stats': stats, # Przekazujemy statystyki do HTML
    }
    
    return render(request, 'app/dashboard.html', context)

# Konfiguracja szablonów (jeśli to nie zostało zrobione globalnie)
TEMPLATES = settings.TEMPLATES
TEMPLATES[0]['DIRS'] = [os.path.join(settings.BASE_DIR, 'templates')]