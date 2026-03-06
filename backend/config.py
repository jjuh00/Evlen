from pydantic_settings import BaseSettings
from pydantic import Field
from pathlib import Path

class Settings(BaseSettings):
    """
    Centralized configuration management using Pydantic's BaseSettings. 
    Validates types and allows loading from environment variables or .env file.
    """

    # JWT settings
    jwt_secret: str = Field(..., alias="JWT_SECRET") # No default, must be set in .env or environment
    jwt_algorithm: str = Field("HS256", alias="JWT_ALGORITHM")
    jwt_expire_minutes: int = Field(120, alias="JWT_EXPIRE_MINUTES")

    # Application environment
    app_env: str = Field("development", alias="APP_ENV")

    # MongoDB connection settings (overridden by docker-compose environment section)
    mongo_url: str = Field("mongodb://mongo:27017", alias="MONGO_URL")
    mongo_db: str = Field("evlen", alias="MONGO_DB")

    @property
    def environment(self) -> str:
        """
        Convenience alias so existing code can refer to settings.environment.
    
        Returns:
            str: The current application environment (e.g., "development", "production").
        """
        return self.app_env

    model_config = {
        "env_file": ".env", # Relative to the working directory
        "case_sensitive": False,
        "populate_by_name": True, # Accept both alias and field name
        "extra": "ignore" # Ignore unknown env vars silently
    }

# Load and validate settings
settings = Settings()

_PLACEHOLDER = "generated_secure_secret_key"

if (
    not settings.jwt_secret or
    settings.jwt_secret == _PLACEHOLDER or
    len(settings.jwt_secret) < 32
):
    raise RuntimeError(
        "JWT_SECRET is not set to a secure value. "
        "Run `python backend/generate_secret.py` to generate one, " 
        "or set the JWT_SECRET environment variable to a secure value (at least 32 characters)"
    )