from typing import Dict, Any


DEVELOPMENT_CONFIG: Dict[str, Any] = {
    "DEBUG": True,
    "FRIDAY_AUTH_DISABLED": True,
    "RATE_LIMIT_ENABLED": False,
    "LOG_LEVEL": "DEBUG",
    "MODEL_NAME": "gemini-2.5-flash",
}

TESTING_CONFIG: Dict[str, Any] = {
    "DEBUG": True,
    "FRIDAY_AUTH_DISABLED": True,
    "RATE_LIMIT_ENABLED": False,
    "LOG_LEVEL": "DEBUG",
    "MODEL_NAME": "gemini-1.5-flash",
}

PRODUCTION_CONFIG: Dict[str, Any] = {
    "DEBUG": False,
    "FRIDAY_AUTH_DISABLED": False,
    "RATE_LIMIT_ENABLED": True,
    "RATE_LIMIT_MAX": 100,
    "RATE_LIMIT_WINDOW": 60,
    "LOG_LEVEL": "INFO",
    "MODEL_NAME": "gemini-2.5-flash",
}

PROFILES: Dict[str, Dict[str, Any]] = {
    "development": DEVELOPMENT_CONFIG,
    "testing": TESTING_CONFIG,
    "production": PRODUCTION_CONFIG,
}


def get_profile_defaults(environment: str) -> Dict[str, Any]:
    return PROFILES.get(environment, DEVELOPMENT_CONFIG).copy()
