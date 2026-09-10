from django.shortcuts import render
from .models import Offer

def offers_dashboard(request):
    # Domyœlnie pobierz wszystkie oferty
    offers = Offer.objects.all()
    
    # Odbieramy parametry z paska adresu (GET)
    tags_input = request.GET.get('tags', '').strip()
    work_mode = request.GET.get('work_mode', '').strip()
    sort_choice = request.GET.get('sort', '').strip()

    # --- FILTROWANIE ---
    if tags_input:
        tags_list = [t.strip() for t in tags_input.split(',')]
        # Filtrujemy po nazwach tagów powi¹zanych z ofert¹
        offers = offers.filter(tags__name__in=tags_list).distinct()
        
    if work_mode:
        offers = offers.filter(work_mode__iexact=work_mode)

    # --- SORTOWANIE ---
    if sort_choice == "date":
        offers = offers.order_by('-published_at')  # Minus oznacza od najnowszych
    elif sort_choice == "highest":
        # Sortowanie po œredniej pensji jest nieco trudniejsze w samym SQL, 
        # ale zazwyczaj wystarczy po prostu posortowaæ po max_salary
        offers = offers.order_by('-salary_max')
    elif sort_choice == "lowest":
        # U¿ywamy F objects aby obs³u¿yæ puste wartoœci (null), ale w prostym wariancie:
        offers = offers.order_by('salary_min')

    context = {
        'offers': offers,
        'count': offers.count(),
        'search_tags': tags_input,
    }
    
    return render(request, 'dashboard.html', context)