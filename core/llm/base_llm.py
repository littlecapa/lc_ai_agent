from typing import Dict, Any
from abc import ABC, abstractmethod
# 🧠 LLM Interface and Implementations
class LLMBase():
    """Abstract base class for all LLM implementations"""
    @abstractmethod
    def __init__(self, api_key: str, model: str, url: str):
        pass

    @abstractmethod
    def query_ai(self, prompt: str, temperature = 0.0, content = "") -> str:
        pass

    @abstractmethod
    def extract_json(self, prompt: str) -> Dict[str, Any]:
        pass

    @abstractmethod
    def get_account_balance(self) -> Dict[str, Any]:
        """Fetch current account balance and usage statistics."""
        pass