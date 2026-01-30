import json
import logging
from typing import Any, Dict, List, Optional

import aiohttp
import requests
from openai import AsyncOpenAI

logger = logging.getLogger(__name__)


class OpenAIClient:
    def __init__(
        self,
        openai_api_key: Optional[str] = None,
        openai_model: str = "gpt-4o-mini",    
        openai_base_url: Optional[str] = None,
    ) -> None:
        self.openai_model = openai_model

        if not openai_api_key:
            raise ValueError("OpenAI API key is required")
        try:
            if openai_base_url:
                self.openai_client = AsyncOpenAI(
                    api_key=openai_api_key,
                    base_url=openai_base_url,
                )
            else:
                self.openai_client = AsyncOpenAI(
                    api_key=openai_api_key
                )

        except Exception as e:
            logger.error(f"Failed to initialize OpenAI client: {e}")
            raise

    async def generate_response(
        self,
        messages: List[Dict[str, str]],
        max_tokens: int = 4000,
        temperature: float = 0.7,
    ) -> str:
        if not self.openai_client:
            raise ValueError(f"OpenAI client is not initialized")
        
        try:
            response = await self.openai_client.chat.completions.create(
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
        return {"role": "system", "content": content}

    def create_user_message(self, content: str) -> Dict[str, str]:
        return {"role": "user", "content": content}

    def create_assistant_message(self, content: str) -> Dict[str, str]:
        return {"role": "assistant", "content": content}