from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    """
    Centralized configuration management using Pydantic's BaseSettings. 
    Validates types and allows loading from environment variables or .env file.
    """

    # JWT settings
    jwt_secret: str = "generated_secure_secret_key"
    jwt_algorithm: str = "HS256"
    jwt_expiration_minutes: int = 120

    # Application environment
    environment: str = "development"

    # MongoDB connection settings (hard-coded in docker-compose)
    mongo_url: str = "mongodb://mongo:27017"
    mongo_db: str = "evlen"

    class Config:
        """
        Loads variables from .env file and allow case-insensitive access.
        """
        env_file = ".env"
        case_sensitive = False

settings = Settings()