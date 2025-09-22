from django.http import JsonResponse
from django.views import View
from django.views.generic import TemplateView
from django.conf import settings
from core.llm.openai_llm import OpenAILLM # Annahme, dass dies vorhanden ist
from core.libs.gmail_processor import run_email_automation
from core.libs.teams_processor import run_channel_automation
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt, csrf_protect
import json
from .models import Category, Page, gmailShareConfig
from .libs.portfolio_stats import get_stats
import os
import logging

logger = logging.getLogger(__name__)

class HomeView(TemplateView):
    """
    Homepage mit Übersicht und Navigation
    """
    template_name = 'home.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Dynamisches Menü definieren
        context['menu_items'] = self.get_menu_items()
        context.update(get_stats())  
        return context
    
    def get_menu_items(self):
        """
        Dynamisches Menü basierend auf Ihrer Liste
        """
        # Ihre Menü-Daten
        menu = [
            ("Dashboard", "/", "fas fa-home"),
            ("Bookmarks", "bookmarks/", "fas fa-bookmark"), 
            ("Ask AI", "ask/", "fas fa-robot"),
            ("Aktien E-Mails", "get_emails/", "fas fa-envelope"),
        ]
        
        # Menü-Items mit aktueller URL vergleichen
        current_path = self.request.path
        menu_items = []
        
        for item in menu:
            if len(item) == 3:
                name, url, icon = item
            else:
                # Fallback falls nur Name und URL gegeben sind
                name, url = item[:2]
                icon = "fas fa-circle"
            
            # Vollständige URL erstellen (relativ zur App)
            if not url.startswith('/'):
                full_url = f"/{url}" if url != "/" else "/"
            else:
                full_url = url
            
            # Prüfen ob aktueller Menüpunkt aktiv ist
            is_active = (current_path == full_url) or (url != "/" and current_path.startswith(f"/{url}"))
            
            menu_items.append({
                'name': name,
                'url': full_url,
                'icon': icon,
                'is_active': is_active
            })
        
        return menu_items
    

def check_openai_llm():
    if settings.OPENAI_LLM == None:
            settings.OPENAI_LLM = OpenAILLM(api_key=settings.OPENAI_API_KEY)

# Create your views here.
def openai_dashboard(request):
    check_openai_llm()
    balance = settings.OPENAI_LLM.get_account_balance()
    return render(request, "dashboard.html", {"balance": balance})

def ask_page(request):
    logger.debug("Rendering ask page")
    return render(request, "ask.html")

@csrf_exempt
def ask_ai_view(request):
    logger.debug(f"Received request to ask AI, Request: {request}")
    logger.debug(f"Request method: {request.method}")
    check_openai_llm()
    if request.method == "POST":
        try:
            body = json.loads(request.body)
            model = body.get("model", "gpt-4o")
            temperature = float(body.get("temperature", 0.7))
            system_content = body.get("content", "You are a helpful assistant.")
            user_prompt = body.get("input", "")

            logger.debug(f"Parameters: {model}, {temperature}, {system_content}, {user_prompt}")

            result = settings.OPENAI_LLM.query_ai(
                prompt = user_prompt, temperature = temperature, content = system_content, model = model)

            return JsonResponse({"result": result})

        except Exception as e:
            logger.error(f"Error in ask_ai_view: {e}")
            return JsonResponse({"error": str(e)}, status=500)
    else:
        logger.error("ask_ai_view received non-POST request")
        return JsonResponse({"error": "Only POST method allowed."}, status=405)

@csrf_protect
def process_emails_view(request):
    config = gmailShareConfig.objects.first()
    logging.debug(f"Using gmailShareConfig: {config}")
    
    """
    Rendert das Formular zum Verarbeiten von E-Mails
    und führt das Skript bei POST-Anfrage aus.
    """
    context = {
        'gmail_user': config.gmail_user,
        'source_folder': config.source_folder,
        'target_folder': config.target_folder,
        'save_path': config.save_path,
        'gmail_password': settings.GMAIL_PASSWORD,
        'message': None, # Für Erfolgs- oder Fehlermeldungen
        'success': False, # Status der Operation
    }

    if request.method == 'POST':
        # Parameter aus dem Formular holen
        gmail_user = request.POST.get('gmail_user')
        gmail_password = request.POST.get('gmail_password')
        source_folder = request.POST.get('source_folder')
        target_folder = request.POST.get('target_folder')
        save_path = request.POST.get('save_path')

        # Die eingegebenen Werte werden immer in den Kontext gesetzt, 
        # damit sie im Formular wieder angezeigt werden (außer dem Passwort).
        context['gmail_user'] = gmail_user
        context['source_folder'] = source_folder
        context['target_folder'] = target_folder
        context['save_path'] = save_path
        context['gmail_password'] = gmail_password

        # Überprüfe, ob alle notwendigen Felder ausgefüllt sind
        if not all([gmail_user, gmail_password, source_folder, target_folder, save_path]):
            context['message'] = "Bitte füllen Sie alle Felder aus."
            context['success'] = False
        else:
            try:
                # Rufe das Python-Skript auf. Es gibt jetzt (True/False, Nachricht) zurück.
                success, message = run_email_automation(
                    gmail_user, gmail_password, source_folder, target_folder, save_path
                )
                context['message'] = message
                context['success'] = success

            except Exception as e:
                # Dies fängt jede Exception ab, die von run_email_automation geworfen wird.
                # run_email_automation selbst fängt GMAIL_LIB_EXCEPTIONs ab und gibt (False, message) zurück,
                # aber für den Fall, dass ein unerwarteter Fehler durchschlägt, fangen wir ihn hier ab.
                logger.error(f"Unerwarteter Fehler in process_emails_view: {e}", exc_info=True)
                context['message'] = f"Ein unerwarteter Fehler ist aufgetreten: {e}"
                context['success'] = False
    
    return render(request, 'get_emails.html', context)

@csrf_protect
def process_channels_view(request):
    """
    Rendert das Formular zum Verarbeiten von Teams-Channels
    und führt den Teams-Extractor bei POST-Anfrage aus.

    Erwartete Felder (alle vorhanden, Validierung je nach Modus):
      - tenant_id (required)
      - client_id (required)
      - client_secret (optional; required wenn use_device_code=False)
      - team (Name oder GUID; required)
      - channel (Name oder GUID; required)
      - save_path (required)
      - use_device_code (Checkbox -> True/False)
    """
    # Standardwerte für die Formularfelder
    default_tenant_id = ""
    default_client_id = ""
    default_team = "Mein Team"
    default_channel = "xyz"
    default_save_path = "/Volumes/Data/DataLake/Finance/TeamsExport"

    context = {
        "tenant_id": default_tenant_id,
        "client_id": default_client_id,
        "team": default_team,
        "channel": default_channel,
        "save_path": default_save_path,
        "use_device_code": True,  # Default: Device Code Flow
        "message": None,
        "success": False,
    }

    if request.method == "POST":
        # Parameter aus dem Formular holen
        tenant_id = (request.POST.get("tenant_id") or "").strip()
        client_id = (request.POST.get("client_id") or "").strip()
        client_secret = (request.POST.get("client_secret") or None)
        team = (request.POST.get("team") or "").strip()
        channel = (request.POST.get("channel") or "").strip()
        save_path = (request.POST.get("save_path") or "").strip()

        # Checkbox: wenn nicht gesetzt, liefert POST kein Feld -> False
        raw_flag = (request.POST.get("use_device_code") or "").lower()
        use_device_code = raw_flag in ("1", "true", "on", "yes")

        # Eingegebene Werte (ohne Secret) wieder in den Kontext
        context.update({
            "tenant_id": tenant_id,
            "client_id": client_id,
            "team": team,
            "channel": channel,
            "save_path": save_path,
            "use_device_code": use_device_code,
        })

        # Validierung
        missing_base = [
            name for name, val in (
                ("tenant_id", tenant_id),
                ("client_id", client_id),
                ("team", team),
                ("channel", channel),
                ("save_path", save_path),
            ) if not val
        ]
        if missing_base:
            context["message"] = f"Bitte füllen Sie alle Pflichtfelder aus: {', '.join(missing_base)}."
            context["success"] = False
            return render(request, "get_channels.html", context)

        if not use_device_code and not client_secret:
            context["message"] = "Wenn Device Code deaktiviert ist, muss ein Client Secret angegeben werden."
            context["success"] = False
            return render(request, "get_channels.html", context)

        # Ausführung
        try:
            logger.info("Starte run_channel_automation für Team '%s' / Channel '%s' (DeviceCode=%s)", team, channel, use_device_code)
            success, message = run_channel_automation(
                tenant_id=tenant_id,
                client_id=client_id,
                client_secret=client_secret,
                team_name_or_id=team,
                channel_name_or_id=channel,
                save_path=save_path,
                use_device_code=use_device_code,
            )
            context["message"] = message
            context["success"] = success
        except Exception as e:
            logger.error("Unerwarteter Fehler in process_channels_view: %s", e, exc_info=True)
            context["message"] = f"Ein unerwarteter Fehler ist aufgetreten: {e}"
            context["success"] = False

    return render(request, "get_channels.html", context)

def bookmark_list_view(request):
    """
    Zeigt alle Lesezeichen an, gruppiert nach Kategorien und sortiert nach Priorität.
    """
    # Rufe alle Kategorien ab und lade die zugehörigen Seiten effizient
    categories = Category.objects.order_by('priority').prefetch_related('pages').all()
    
    context = {
        'categories': categories
    }
    return render(request, 'bookmarks_list.html', context)
