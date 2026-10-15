from enum import Enum


class LLMProvider(str, Enum):
    OLLAMA = "ollama"
    CLAUDE = "claude"
