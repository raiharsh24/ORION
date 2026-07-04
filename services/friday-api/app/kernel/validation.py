import os
from typing import List
from loguru import logger


def validate_startup(config: object) -> List[str]:
    errors: List[str] = []

    try:
        workspace_root = getattr(config.paths, "workspace_root", None)
        if workspace_root:
            if not os.path.exists(workspace_root):
                errors.append(f"WARNING: workspace_root '{workspace_root}' does not exist")
    except Exception as e:
        errors.append(f"workspace_root check failed: {e}")

    try:
        persist_dir = getattr(config.paths, "persist_dir", None)
        if persist_dir:
            if not os.path.exists(persist_dir):
                os.makedirs(persist_dir, exist_ok=True)
                logger.info(f"Created persist_dir: {persist_dir}")
    except Exception as e:
        errors.append(f"persist_dir setup failed: {e}")

    from app.core.config import settings

    if not settings.GEMINI_API_KEY and not settings.OPENAI_API_KEY:
        errors.append("WARNING: No LLM API keys configured (GEMINI_API_KEY, OPENAI_API_KEY)")

    if not settings.FRIDAY_SECRET_KEY:
        errors.append("WARNING: FRIDAY_SECRET_KEY is not set - HMAC signing will be unavailable")

    if not settings.FRIDAY_API_KEY and not settings.FRIDAY_AUTH_DISABLED:
        errors.append("WARNING: FRIDAY_API_KEY is not set and auth is enabled - all API requests will be rejected")

    if settings.TEMPERATURE < 0.0 or settings.TEMPERATURE > 2.0:
        errors.append(f"WARNING: TEMPERATURE={settings.TEMPERATURE} is outside recommended range [0.0, 2.0]")

    if settings.MAX_TOKENS < 1:
        errors.append(f"WARNING: MAX_TOKENS={settings.MAX_TOKENS} is invalid")

    n_models_config = getattr(config, "models", None)
    if n_models_config:
        default_llm = getattr(n_models_config, "default_llm", None)
        if default_llm and "gemini" not in default_llm and "gpt" not in default_llm:
            errors.append(f"WARNING: Unrecognized default_llm='{default_llm}'")

    return errors
