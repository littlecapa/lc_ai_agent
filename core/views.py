from django.http import JsonResponse
from django.views import View
from django.conf import settings
from core.llm.openai_llm import OpenAILLM # Annahme, dass dies vorhanden ist
from core.libs.gmail_processor import run_email_automation
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
import json

import logging

logger = logging.getLogger(__name__)

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
    
def process_emails_view(request):
    """
    Rendert das Formular zum Verarbeiten von E-Mails
    und führt das Skript bei POST-Anfrage aus.
    """
    # Standardwerte für die Formularfelder
    default_gmail_user = "littlecapa@googlemail.com"
    default_source_folder = "Aktien"
    default_target_folder = "Archive_Aktien"
    # Achtung: Pfad an dein System anpassen!
    default_save_path = "/Volumes/Data/DataLake/Finance/Test" 

    context = {
        'gmail_user': default_gmail_user,
        'source_folder': default_source_folder,
        'target_folder': default_target_folder,
        'save_path': default_save_path,
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
