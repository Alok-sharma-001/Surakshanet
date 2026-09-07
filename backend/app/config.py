import json
from functools import lru_cache
from typing import Any, List, Optional
from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    APP_NAME: str = "Surakshanet"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    ENVIRONMENT: str = "development"
    API_PREFIX: str = "/api/v1"
    
    POSTGRES_USER: str = "surakshanet"
    POSTGRES_PASSWORD: str = "surakshanet_dev"
    POSTGRES_DB: str = "surakshanet"
    POSTGRES_HOST: str = "postgres"
    POSTGRES_PORT: str = "5432"
    
    DATABASE_URL: Optional[str] = None
    
    REDIS_URL: str = "redis://redis:6379/0"
    
    MQTT_BROKER_HOST: str = "mosquitto"
    MQTT_BROKER_PORT: int = 1883
    MQTT_USERNAME: Optional[str] = None
    MQTT_PASSWORD: Optional[str] = None
    
    JWT_SECRET_KEY: str = "your-super-secret-key-change-in-production"
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    
    ADMIN_EMAIL: str = "admin@surakshanet.local"
    ADMIN_PASSWORD: str = "SurakshaNet@2026"

    CORS_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://localhost:5173",
        "https://localhost",
        "https://127.0.0.1",
    ]
    
    SUMO_HOME: str = "/usr/share/sumo"
    SUMO_BINARY: str = "sumo"

    model_config = SettingsConfigDict(env_file=".env", case_sensitive=False, extra="ignore")

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def parse_cors_origins(cls, v: Any) -> List[str]:
        if isinstance(v, str):
            v_strip = v.strip()
            if v_strip.startswith("[") and v_strip.endswith("]"):
                try:
                    parsed = json.loads(v_strip)
                    if isinstance(parsed, list):
                        return [str(origin).strip() for origin in parsed if str(origin).strip()]
                except json.JSONDecodeError:
                    pass
            return [origin.strip() for origin in v.split(",") if origin.strip()]
        elif isinstance(v, (list, tuple, set)):
            return [str(origin).strip() for origin in v if str(origin).strip()]
        return v

    @field_validator("CORS_ORIGINS", mode="after")
    @classmethod
    def sanitize_cors_origins(cls, v: List[str]) -> List[str]:
        cleaned = [origin for origin in v if origin != "*"]
        if not cleaned:
            return [
                "http://localhost:3000",
                "http://localhost:5173",
                "https://localhost",
                "https://127.0.0.1",
            ]
        return cleaned

    @model_validator(mode="after")
    def assemble_database_url(self) -> 'Settings':
        if not self.DATABASE_URL:
            self.DATABASE_URL = (
                f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
                f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
            )
        return self

    @model_validator(mode="after")
    def validate_production_secrets(self) -> 'Settings':
        if self.ENVIRONMENT.lower() == "production":
            insecure_jwt_defaults = {
                "your-super-secret-key-change-in-production",
                "secret",
                "changeme",
                "change-me",
                "",
            }
            if self.JWT_SECRET_KEY in insecure_jwt_defaults or len(self.JWT_SECRET_KEY) < 16:
                raise ValueError(
                    "Production environment requires a secure, non-default JWT_SECRET_KEY (min 16 chars)"
                )

            insecure_passwords = {
                "SurakshaNet@2026",
                "Alok@2005",
                "admin",
                "admin123",
                "password",
                "12345678",
                "",
            }
            if self.ADMIN_PASSWORD in insecure_passwords or len(self.ADMIN_PASSWORD) < 8:
                raise ValueError(
                    "Production environment requires a strong, non-default ADMIN_PASSWORD (min 8 chars)"
                )

            if self.DATABASE_URL and "surakshanet_dev" in self.DATABASE_URL:
                raise ValueError(
                    "Production environment cannot use default development database credentials ('surakshanet_dev')"
                )
        return self

@lru_cache()
def get_settings() -> Settings:
    return Settings()
