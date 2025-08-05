# core/urls.py
from django.urls import path
from .views import openai_dashboard, ask_ai_view, ask_page 

urlpatterns = [
    path("api/ask/", ask_ai_view, name="ask_ai"),
    path("ask/", ask_page, name="ask-page"),
    path("dashboard/", openai_dashboard, name="openai-dashboard"),
]
