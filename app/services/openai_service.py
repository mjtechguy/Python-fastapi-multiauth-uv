"""OpenAI and LLM integration service with provider abstraction."""

from typing import Any, AsyncIterator

import httpx
from openai import AsyncOpenAI

from app.core.config import settings


class LLMProvider:
    """Base class for LLM providers."""

    async def chat_completion(
        self, messages: list[dict[str, str]], **kwargs: Any
    ) -> dict[str, Any]:
        """Create a chat completion."""
        raise NotImplementedError

    async def chat_completion_stream(
        self, messages: list[dict[str, str]], **kwargs: Any
    ) -> AsyncIterator[dict[str, Any]]:
        """Create a streaming chat completion."""
        raise NotImplementedError


class OpenAIProvider(LLMProvider):
    """OpenAI API provider."""

    def __init__(self, api_key: str | None = None, base_url: str | None = None):
        """Initialize OpenAI client."""
        self.client = AsyncOpenAI(
            api_key=api_key or settings.OPENAI_API_KEY,
            base_url=base_url or settings.OPENAI_API_BASE,
        )

    async def chat_completion(
        self, messages: list[dict[str, str]], **kwargs: Any
    ) -> dict[str, Any]:
        """Create a chat completion using OpenAI."""
        model = kwargs.pop("model", settings.OPENAI_MODEL)
        max_tokens = kwargs.pop("max_tokens", settings.OPENAI_MAX_TOKENS)

        response = await self.client.chat.completions.create(
            model=model, messages=messages, max_tokens=max_tokens, **kwargs
        )

        return {
            "content": response.choices[0].message.content,
            "role": response.choices[0].message.role,
            "model": response.model,
            "usage": {
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens,
            },
        }

    async def chat_completion_stream(
        self, messages: list[dict[str, str]], **kwargs: Any
    ) -> AsyncIterator[dict[str, Any]]:
        """Create a streaming chat completion using OpenAI."""
        model = kwargs.pop("model", settings.OPENAI_MODEL)
        max_tokens = kwargs.pop("max_tokens", settings.OPENAI_MAX_TOKENS)

        stream = await self.client.chat.completions.create(
            model=model, messages=messages, max_tokens=max_tokens, stream=True, **kwargs
        )

        async for chunk in stream:
            if chunk.choices[0].delta.content:
                yield {
                    "content": chunk.choices[0].delta.content,
                    "model": chunk.model,
                }


class OpenAICompatibleProvider(LLMProvider):
    """Provider for OpenAI-compatible APIs (e.g., Together AI, Anyscale)."""

    def __init__(self, api_key: str, base_url: str):
        """Initialize OpenAI-compatible client."""
        self.client = AsyncOpenAI(api_key=api_key, base_url=base_url)

    async def chat_completion(
        self, messages: list[dict[str, str]], **kwargs: Any
    ) -> dict[str, Any]:
        """Create a chat completion using OpenAI-compatible API."""
        model = kwargs.pop("model", "default")
        max_tokens = kwargs.pop("max_tokens", 2000)

        response = await self.client.chat.completions.create(
            model=model, messages=messages, max_tokens=max_tokens, **kwargs
        )

        return {
            "content": response.choices[0].message.content,
            "role": response.choices[0].message.role,
            "model": response.model,
            "usage": {
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens,
            },
        }

    async def chat_completion_stream(
        self, messages: list[dict[str, str]], **kwargs: Any
    ) -> AsyncIterator[dict[str, Any]]:
        """Create a streaming chat completion."""
        model = kwargs.pop("model", "default")
        max_tokens = kwargs.pop("max_tokens", 2000)

        stream = await self.client.chat.completions.create(
            model=model, messages=messages, max_tokens=max_tokens, stream=True, **kwargs
        )

        async for chunk in stream:
            if chunk.choices[0].delta.content:
                yield {
                    "content": chunk.choices[0].delta.content,
                    "model": chunk.model,
                }


class LLMService:
    """Service for LLM interactions with multiple provider support."""

    def __init__(self, provider: LLMProvider | None = None):
        """Initialize LLM service with a provider."""
        self.provider = provider or OpenAIProvider()

    async def generate_text(
        self,
        prompt: str,
        system_message: str | None = None,
        **kwargs: Any,
    ) -> str:
        """
        Generate text using the LLM.

        Args:
            prompt: User prompt
            system_message: Optional system message
            **kwargs: Additional arguments for the provider

        Returns:
            Generated text
        """
        messages = []

        if system_message:
            messages.append({"role": "system", "content": system_message})

        messages.append({"role": "user", "content": prompt})

        response = await self.provider.chat_completion(messages, **kwargs)
        return response["content"]

    async def generate_text_stream(
        self,
        prompt: str,
        system_message: str | None = None,
        **kwargs: Any,
    ) -> AsyncIterator[str]:
        """
        Generate text using the LLM with streaming.

        Args:
            prompt: User prompt
            system_message: Optional system message
            **kwargs: Additional arguments for the provider

        Yields:
            Text chunks
        """
        messages = []

        if system_message:
            messages.append({"role": "system", "content": system_message})

        messages.append({"role": "user", "content": prompt})

        async for chunk in self.provider.chat_completion_stream(messages, **kwargs):
            yield chunk["content"]

    async def chat(
        self,
        messages: list[dict[str, str]],
        **kwargs: Any,
    ) -> dict[str, Any]:
        """
        Have a conversation with the LLM.

        Args:
            messages: List of messages in the conversation
            **kwargs: Additional arguments for the provider

        Returns:
            Response dictionary
        """
        return await self.provider.chat_completion(messages, **kwargs)

    async def chat_stream(
        self,
        messages: list[dict[str, str]],
        **kwargs: Any,
    ) -> AsyncIterator[dict[str, Any]]:
        """
        Have a streaming conversation with the LLM.

        Args:
            messages: List of messages in the conversation
            **kwargs: Additional arguments for the provider

        Yields:
            Response chunks
        """
        async for chunk in self.provider.chat_completion_stream(messages, **kwargs):
            yield chunk


# Default LLM service instance
llm_service = LLMService()
