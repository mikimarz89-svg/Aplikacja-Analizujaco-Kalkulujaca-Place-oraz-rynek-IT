"""
Definition of urls for DjangoWebProject1.
"""

from datetime import datetime
from django.urls import path
from django.contrib import admin
from django.contrib.auth.views import LoginView, LogoutView
from app import forms, views

urlpatterns = [
    # Twoja nowa strona g³ówna z ofertami:
    path('', views.offers_dashboard, name='home'),
    
    # TE DWIE LINIJKI ZOSTA£Y ZAKOMENTOWANE, ¯EBY NIE POWODOWAÆ B£ÊDU:
    # path('contact/', views.contact, name='contact'),
    # path('about/', views.about, name='about'),
    
    path('login/',
         LoginView.as_view
         (
             template_name='app/login.html',
             authentication_form=forms.BootstrapAuthenticationForm,
             extra_context=
             {
                 'title': 'Log in',
                 'year' : datetime.now().year,
             }
         ),
         name='login'),
    path('logout/', LogoutView.as_view(next_page='/'), name='logout'),
    path('admin/', admin.site.urls),
]