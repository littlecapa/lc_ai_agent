from django.http import JsonResponse
from django.views import View
from django.conf import settings
from core.llm.openai_llm import OpenAILLM
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
