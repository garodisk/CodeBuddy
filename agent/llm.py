"""Centralized LLM configuration."""
import os
from langchain_openai import ChatOpenAI


def get_llm(temperature: float = 0.0, streaming: bool = True) -> ChatOpenAI:
    """Get configured LLM instance."""
    model = os.getenv("CODER_BUDDY_MODEL", "gpt-4o")
    return ChatOpenAI(
        model=model,
        temperature=temperature,
        streaming=streaming,
    )


# Default instances for common use cases
llm = get_llm(temperature=0.0)  # For structured outputs (planner, architect)
chat_llm = get_llm(temperature=0.7)  # For conversational chat
