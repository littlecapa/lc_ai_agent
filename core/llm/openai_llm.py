# 🔹 OpenAI LLM
import openai
from .base_llm import LLMBase
from typing import Dict, Any
import json
import requests

import logging

logger = logging.getLogger(__name__)

class OpenAILLM(LLMBase):
    def __init__(self, api_key: str, model: str = "gpt-4o", url: str = "https://api.openai.com/v1"):
        self.api_key = api_key
        self.model = model
        self.client = openai.OpenAI(api_key=api_key)
        self.url = url

    def query_ai(self, prompt: str, temperature=0.0, content="", model=None) -> str:
        if model is None:
            model = self.model
        try:
            logger.debug(f"🔍 Querying OpenAI with model: {model}, temperature: {temperature}, content: {content}, prompt: {prompt}")
            response = self.client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": content},
                    {"role": "user", "content": prompt}
                ],
                temperature=temperature
            )
            logger.debug("✅ DEBUG: Back in Query Function")
            logger.debug(f"✅ DEBUG: OpenAI raw response: {response}")
            logger.debug(f"Nach response")  
            if (
                response
                and hasattr(response, "choices")
                and len(response.choices) > 0
                and hasattr(response.choices[0], "message")
                and hasattr(response.choices[0].message, "content")
            ):
                return response.choices[0].message.content.strip()
    
            logger.error(f"⚠️ Unexpected OpenAI response format: {response}")
            return ""
        except Exception as e:
            logger.error(f"❌ Error querying OpenAI: {e}")
            return ""


    def extract_json(self, prompt: str) -> Dict[str, Any]:
        response = self.query_ai(
            prompt = prompt,
            temperature = 0.0,
            content = "Extract structured financial data in JSON format. Include currency if given, otherwise assume EUR.")
        content = response.choices[0].message.content
        try:
            content_clean = content.strip()
            if content_clean.startswith("```json"):
                content_clean = content_clean.replace("```json", "").replace("```", "").strip()
            return json.loads(content_clean)
        except json.JSONDecodeError:
            return {"error": "Failed to parse JSON", "raw_output": content}
        
    def get_account_balance(self) -> Dict[str, Any]:
        """Fetch current OpenAI account balance and usage."""
        try:
            headers = {
                "Authorization": f"Bearer {self.api_key}"
            }

            # 1. Check subscription
            sub_resp = requests.get(
                self.url+"/dashboard/billing/subscription",
                headers=headers,
                timeout=10
            )
            sub_data = sub_resp.json()

            # 2. Check usage (current billing cycle)
            usage_resp = requests.get(
                self.url+"/dashboard/billing/usage",
                headers=headers,
                timeout=10,
                params={
                    "start_date": "2025-07-01",  # Use current month start
                    "end_date": "2025-07-31"     # Replace with today's date
                }
            )
            usage_data = usage_resp.json()

            return {
                "hard_limit_usd": sub_data.get("hard_limit_usd"),
                "used_usd": round(usage_data.get("total_usage", 0) / 100.0, 2),
                "remaining_usd": round(
                    sub_data.get("hard_limit_usd", 0) - usage_data.get("total_usage", 0) / 100.0,
                    2
                )
            }

        except Exception as e:
            return {"error": str(e)}