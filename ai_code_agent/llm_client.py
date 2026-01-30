"""LLM client for interacting with OpenAI."""

import json
import logging
from typing import Any, Dict, List, Optional

import aiohttp
import requests
from openai import OpenAI

# Configuration will be passed as parameters instead of importing global config

logger = logging.getLogger(__name__)


class LLMClient:
    """Client for interacting with Language Learning Models."""

    def __init__(
        self,
        openai_api_key: Optional[str] = None,
        openai_model: str = "gpt-4",    
        openai_base_url: str = ""
    ) -> None:
        """Initialize the LLM client."""
        self.openai_model = openai_model
        
        if not openai_api_key:
            raise ValueError("OpenAI API key is required")
        try:
            # Try to create OpenAI client with minimal parameters to avoid compatibility issues
            self.openai_client = OpenAI(
                api_key=openai_api_key,
                base_url=openai_base_url
            )
        except Exception as e:
            logger.error(f"Failed to initialize {openai_base_url} OpenAI client: {e}")
            # Fallback: set to None and handle gracefully
            self.openai_client = None

    async def generate_response(
        self,
        messages: List[Dict[str, str]],
        max_tokens: int = 4000,
        temperature: float = 0.7,
    ) -> str:
        """Generate a response using the configured LLM."""
        return self._generate_openai_response(messages, max_tokens, temperature)

    def _generate_openai_response(
        self,
        messages: List[Dict[str, str]],
        max_tokens: int,
        temperature: float,
    ) -> str:
        """Generate response using OpenAI API."""
        if not self.openai_client:
            raise ValueError("OpenAI client is not initialized")
        
        try:
            response = self.openai_client.chat.completions.create(
                model=self.openai_model,
                messages=messages,
                max_tokens=max_tokens,
                temperature=temperature,
            )
            return response.choices[0].message.content or ""
        except Exception as e:
            logger.error(f"Error generating OpenAI response: {e}")
            raise

    def create_system_message(self, content: str) -> Dict[str, str]:
        """Create a system message."""
        return {"role": "system", "content": content}

    def create_user_message(self, content: str) -> Dict[str, str]:
        """Create a user message."""
        return {"role": "user", "content": content}

    def create_assistant_message(self, content: str) -> Dict[str, str]:
        """Create an assistant message."""
        return {"role": "assistant", "content": content}