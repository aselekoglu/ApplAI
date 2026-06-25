from __future__ import annotations

from typing import Any, Dict, Optional

try:
    from google import genai
except ImportError:  # pragma: no cover - exercised only when dependency is absent locally.
    class _MissingGenai:
        class Client:  # noqa: N801 - mirrors google.genai.Client for patching in tests.
            def __init__(self, *args: Any, **kwargs: Any) -> None:
                raise RuntimeError("google-genai is not installed. Install requirements.txt before calling Gemini.")

    genai = _MissingGenai()

from pydantic import BaseModel, Field

from api.app.config import settings


class GeminiInteractionRequest(BaseModel):
    input: str = Field(..., min_length=1)
    model: str = ""
    system_instruction: str = ""
    temperature: Optional[float] = None
    thinking_level: Optional[str] = None
    previous_interaction_id: Optional[str] = None
    store: bool = False
    background: bool = False


def _generation_config(request: GeminiInteractionRequest) -> Dict[str, Any] | None:
    config: Dict[str, Any] = {}
    if request.temperature is not None:
        config["temperature"] = request.temperature
    if request.thinking_level:
        config["thinking_level"] = request.thinking_level
    return config or None


def create_text_interaction(request: GeminiInteractionRequest) -> Dict[str, Any]:
    if request.background and not request.store:
        raise ValueError(
            "Gemini background execution requires store=true; keep private ApplAI CV/JD tasks on the local queue."
        )

    client = genai.Client()
    kwargs: Dict[str, Any] = {
        "model": request.model.strip() or settings.gemini_default_model,
        "input": request.input,
        "store": request.store,
    }
    if request.system_instruction:
        kwargs["system_instruction"] = request.system_instruction
    if request.previous_interaction_id:
        kwargs["previous_interaction_id"] = request.previous_interaction_id
    if request.background:
        kwargs["background"] = True
    generation_config = _generation_config(request)
    if generation_config:
        kwargs["generation_config"] = generation_config

    interaction = client.interactions.create(**kwargs)
    if hasattr(interaction, "model_dump"):
        payload = interaction.model_dump()
    else:
        payload = {"id": getattr(interaction, "id", ""), "output_text": getattr(interaction, "output_text", "")}
    payload["output_text"] = getattr(interaction, "output_text", payload.get("output_text", ""))
    return payload
