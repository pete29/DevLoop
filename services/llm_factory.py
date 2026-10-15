from config.settings import (
    Settings,
)
from services.claude_service import (
    ClaudeService,
)
from services.llm_provider import (
    LLMProvider,
)
from services.ollama_service import (
    OllamaService,
)


class LLMFactory:

    @classmethod
    def create(cls, role: str = ""):
        """The model for one agent.

        The role only matters for Claude, where judgement
        (planning, review) and volume (writing files,
        writing tests) are worth different models.
        """

        if Settings.LLM_PROVIDER == LLMProvider.CLAUDE:
            return ClaudeService(
                model=Settings.CLAUDE_MODELS.get(
                    role,
                    Settings.CLAUDE_MODEL,
                ),
                effort=Settings.CLAUDE_EFFORTS.get(
                    role,
                    Settings.CLAUDE_EFFORT,
                ),
                role=role,
            )

        return OllamaService(
            model=Settings.OLLAMA_MODEL,
            role=role,
        )
