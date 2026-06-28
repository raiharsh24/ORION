import os
from typing import Dict, Any, Type
from pydantic import ValidationError
from loguru import logger
from app.kernel.config import FridayKernelConfig

class FridayConfigSystem:
    """
    Centralized configuration manager supporting typed settings, validation,
    default fallbacks, and environment variable overrides.
    """
    def __init__(self, config_input: Any = None) -> None:
        if isinstance(config_input, FridayKernelConfig):
            self._config = config_input
        else:
            self._config_class = config_input or FridayKernelConfig
            self._config = self._load_initial_config()

    def _load_initial_config(self) -> FridayKernelConfig:
        """Loads and resolves initial config with environment and core settings overrides."""
        config_obj = self._config_class()
        
        # Load from app.core.config.settings
        from app.core.config import settings as core_settings
        config_obj.api_keys.gemini_api_key = core_settings.GEMINI_API_KEY
        config_obj.models.default_llm = core_settings.MODEL_NAME

        # Override properties from environment variables if present
        workspace_env = os.getenv("WORKSPACE_ROOT")
        if workspace_env:
            config_obj.paths.workspace_root = workspace_env
            
        gemini_env = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        if gemini_env:
            config_obj.api_keys.gemini_api_key = gemini_env
            
        model_env = os.getenv("MODEL_NAME")
        if model_env:
            config_obj.models.default_llm = model_env
            
        return config_obj

    def get_config(self) -> FridayKernelConfig:
        """Returns the current loaded typed configuration instance."""
        return self._config

    def update_config(self, updates: Dict[str, Any]) -> FridayKernelConfig:
        """
        Dynamically applies updates, validating the new configuration model.
        Raises ValidationError if validation checks fail.
        """
        try:
            # Pydantic v2 model_dump()
            current_dict = self._config.model_dump()
            
            # Recursive dictionary update helper
            def merge_dicts(d1: dict, d2: dict) -> None:
                for k, v in d2.items():
                    if isinstance(v, dict) and k in d1 and isinstance(d1[k], dict):
                        merge_dicts(d1[k], v)
                    else:
                        d1[k] = v
            
            merge_dicts(current_dict, updates)
            # Re-validate against Pydantic schema
            self._config = self._config_class(**current_dict)
            logger.info("System configuration updated and validated.")
            return self._config
        except ValidationError as e:
            logger.error(f"System configuration validation failed: {str(e)}")
            raise e
