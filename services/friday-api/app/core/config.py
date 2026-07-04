from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", 
        env_file_encoding="utf-8", 
        extra="ignore"
    )

    APP_NAME: str = "FRIDAY API"
    APP_VERSION: str = "0.3.0"
    DEBUG: bool = False
    ENVIRONMENT: str = "development"
    
    GEMINI_API_KEY: str | None = None
    OPENAI_API_KEY: str | None = None

    # Model Generation Config Options (v0.4)
    MODEL_NAME: str = "gemini-1.5-flash"
    TEMPERATURE: float = 0.7
    MAX_TOKENS: int = 2048
    TOP_P: float = 0.95

    # Security
    FRIDAY_API_KEY: str = ""
    FRIDAY_SECRET_KEY: str = ""
    FRIDAY_AUTH_DISABLED: bool = True

    # Rate Limiting
    RATE_LIMIT_ENABLED: bool = False
    RATE_LIMIT_MAX: int = 100
    RATE_LIMIT_WINDOW: int = 60

    # Logging
    LOG_LEVEL: str = "DEBUG"

    # Release metadata (set via env in CI/CD)
    BUILD_HASH: str = "development"
    BUILD_COMMIT: str = "HEAD"
    BUILD_DATE: str = ""

settings = Settings()
