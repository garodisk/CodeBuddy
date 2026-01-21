"""Centralized LLM configuration with multi-provider support."""
import os
from typing import Any


def get_provider() -> str:
    """Get the configured LLM provider."""
    return os.getenv("LLM_PROVIDER", "openai").lower()


def get_model_for_provider(provider: str) -> str:
    """Get the default model for a provider."""
    defaults = {
        "openai": "gpt-4o",
        "anthropic": "claude-sonnet-4-20250514",
        "gemini": "gemini-1.5-pro",
        "groq": "llama-3.3-70b-versatile",
        "openrouter": "anthropic/claude-sonnet-4",
    }
    # Allow override via environment variable
    env_model = os.getenv("LLM_MODEL")
    if env_model:
        return env_model
    return defaults.get(provider, "gpt-4o")


def get_llm(temperature: float = 0.0, streaming: bool = True) -> Any:
    """Get configured LLM instance based on provider."""
    provider = get_provider()
    model = get_model_for_provider(provider)

    if provider == "openai":
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(
            model=model,
            temperature=temperature,
            streaming=streaming,
        )

    elif provider == "anthropic":
        from langchain_anthropic import ChatAnthropic
        return ChatAnthropic(
            model=model,
            temperature=temperature,
            streaming=streaming,
        )

    elif provider == "gemini":
        from langchain_google_genai import ChatGoogleGenerativeAI
        return ChatGoogleGenerativeAI(
            model=model,
            temperature=temperature,
            streaming=streaming,
        )

    elif provider == "groq":
        from langchain_groq import ChatGroq
        return ChatGroq(
            model=model,
            temperature=temperature,
            streaming=streaming,
        )

    elif provider == "openrouter":
        from langchain_openai import ChatOpenAI
        api_key = os.getenv("OPENROUTER_API_KEY")
        return ChatOpenAI(
            model=model,
            temperature=temperature,
            streaming=streaming,
            openai_api_key=api_key,
            openai_api_base="https://openrouter.ai/api/v1",
        )

    else:
        # Default to OpenAI
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(
            model=model,
            temperature=temperature,
            streaming=streaming,
        )


def get_provider_info() -> dict:
    """Get info about the current provider configuration."""
    provider = get_provider()
    model = get_model_for_provider(provider)
    return {
        "provider": provider,
        "model": model,
    }


# Default instances for common use cases
llm = get_llm(temperature=0.0)  # For structured outputs (planner, architect)
chat_llm = get_llm(temperature=0.7)  # For conversational chat
