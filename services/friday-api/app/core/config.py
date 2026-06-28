from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", 
        env_file_encoding="utf-8", 
        extra="ignore"
    )

    APP_NAME: str = "FRIDAY API"
    APP_VERSION: str = "0.2"
    DEBUG: bool = False
    
    GEMINI_API_KEY: str | None = None
    OPENAI_API_KEY: str | None = None

    # Model Generation Config Options (v0.4)
    MODEL_NAME: str = "gemini-1.5-flash"
    TEMPERATURE: float = 0.7
    MAX_TOKENS: int = 2048
    TOP_P: float = 0.95

settings = Settings()
