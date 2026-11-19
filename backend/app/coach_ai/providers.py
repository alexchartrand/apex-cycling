"""Which model provider runs the AI coach (`AI_COACH_PROVIDER`), and the one
place a client for it is built. The athlete's consent names the provider
(`AiCoachAccess.consent_provider`): switching provider asks for it again,
since the data then goes to another company."""

from app.coach_ai.ports import LlmClientPort
from app.core.config import get_settings

LABELS = {"mistral": "Mistral AI", "anthropic": "Anthropic"}


def current_provider() -> str:
    return get_settings().ai_coach_provider


def provider_label() -> str:
    return LABELS[current_provider()]


def ai_coach_available() -> bool:
    settings = get_settings()
    if current_provider() == "anthropic":
        return bool(settings.anthropic_api_key)
    return bool(settings.mistral_api_key)


def current_model() -> str:
    settings = get_settings()
    return settings.anthropic_model if current_provider() == "anthropic" else settings.mistral_model


def prices_for_model(model: str) -> tuple[float, float, float, float]:
    """USD per million tokens: (input, output, cache read, cache write), by
    the provider that served `model` (a usage row may predate a switch)."""
    settings = get_settings()
    if model.startswith("claude"):
        return (
            settings.anthropic_price_input_per_mtok,
            settings.anthropic_price_output_per_mtok,
            settings.anthropic_price_cache_read_per_mtok,
            settings.anthropic_price_cache_write_per_mtok,
        )
    price = settings.mistral_price_input_per_mtok
    return price, settings.mistral_price_output_per_mtok, price, price


def build_llm_client() -> LlmClientPort:
    if current_provider() == "anthropic":
        from app.coach_ai.anthropic_client import AnthropicClient

        return AnthropicClient()
    from app.coach_ai.client import MistralClient

    return MistralClient()
