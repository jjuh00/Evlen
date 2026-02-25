from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    jwt_secret: str = "generated_secure_secret_key"
    jwt_algorithm: str = "HS256"
    jwt_expiration_minutes: int = 120

    environment: str = "development"

    mongo_url: str = "mongodb://mongo:27017"
    mongo_db: str = "evlen"

    class Config:
        env_file = ".env"
        case_sensitive = False

settings = Settings()