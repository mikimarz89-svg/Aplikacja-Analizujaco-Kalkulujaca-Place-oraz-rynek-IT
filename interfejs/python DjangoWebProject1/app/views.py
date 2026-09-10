from django.shortcuts import render, redirect
from django.http import HttpResponseBadRequest
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_protect
from django.db.models import Avg, Min, Max
from .models import Offer
import statistics
import inspect
import json

# import registry z main.py
from . import main as console_main

def offers_dashboard(request):
    offers = Offer.objects.all()
    tags_input = request.GET.get('tags', '').strip()
    work_mode = request.GET.get('work_mode', '').strip()
    sort_choice = request.GET.get('sort', '').strip()
    logic_mode = request.GET.get('mode', 'OR').strip().upper()

    if tags_input:
        tags_list = [t.strip() for t in tags_input.split(',')]
        if logic_mode == 'AND':
            for tag in tags_list:
                offers = offers.filter(tags__name__iexact=tag)
        else:
            offers = offers.filter(tags__name__in=tags_list).distinct()
    if work_mode:
        offers = offers.filter(work_mode__iexact=work_mode)

    if sort_choice == "date":
        offers = offers.order_by('-published_at')
    elif sort_choice == "highest":
        offers = offers.order_by('-salary_max')
    elif sort_choice == "lowest":
        offers = offers.order_by('salary_min')

    stats = None
    if offers.exists() and tags_input:
        db_stats = offers.aggregate(
            avg_salary=Avg('salary_min'),
            min_salary=Min('salary_min'),
            max_salary=Max('salary_max')
        )
        salaries = list(offers.values_list('salary_min', flat=True))
        salaries = [s for s in salaries if s is not None]
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
        'stats': stats,
    }
    return render(request, 'app/dashboard.html', context)

# ---- API webowy dla funkcji z main.py ----
def functions_list(request):
    """
    Wyœwietla listê funkcji dostêpnych do wywo³ania.
    """
    funcs = []
    for name, fn in getattr(console_main, 'EXPOSED_FUNCTIONS', {}).items():
        try:
            sig = str(inspect.signature(fn))
        except (ValueError, TypeError):
            sig = "(brak sygnatury)"
        funcs.append({'name': name, 'signature': sig})
    return render(request, 'app/functions_list.html', {'functions': funcs})

@csrf_protect
@require_http_methods(["GET", "POST"])
def invoke_function(request, name):
    """
    Formularz wywo³ania funkcji oraz obs³uga POST (wynik).
    POST oczekuje pola 'payload' zawieraj¹cego JSON: lista pozycyjnych arg lub s³ownik kwargs.
    Przyk³ady payload:
      - []               -> brak argumentów
      - [1,2]            -> args
      - {"x":1,"y":2}    -> kwargs
    """
    registry = getattr(console_main, 'EXPOSED_FUNCTIONS', {})
    if name not in registry:
        return HttpResponseBadRequest("Funkcja niedozwolona lub nieznana.")

    fn = registry[name]
    if request.method == "POST":
        payload = request.POST.get('payload', '').strip()
        try:
            parsed = json.loads(payload) if payload else []
        except json.JSONDecodeError as e:
            return render(request, 'app/invoke_result.html', {'name': name, 'error': f'B³¹d JSON: {e}'})

        try:
            if isinstance(parsed, list):
                result = fn(*parsed)
            elif isinstance(parsed, dict):
                result = fn(**parsed)
            else:
                return render(request, 'app/invoke_result.html', {'name': name, 'error': 'Payload musi byæ list¹ lub obiektem JSON.'})
            # Spróbuj sformatowaæ wynik do JSON-serializable stringa
            try:
                result_display = json.dumps(result, default=str, ensure_ascii=False)
            except Exception:
                result_display = str(result)
            return render(request, 'app/invoke_result.html', {'name': name, 'result': result_display})
        except Exception as e:
            return render(request, 'app/invoke_result.html', {'name': name, 'error': str(e)})

    # GET -> wyœwietl formularz z sygnatur¹
    try:
        signature = str(inspect.signature(fn))
    except Exception:
        signature = ''
    return render(request, 'app/invoke_form.html', {'name': name, 'signature': signature})