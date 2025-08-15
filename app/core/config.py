# app/core/config.py
import os
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict
from dotenv import load_dotenv

load_dotenv()

class Settings(BaseSettings):
    # # Base configuration
    PROJECT_NAME: str = "Otzar AI Gateway"
    # API_V1_STR: str = "/api/v1"
    
    # # Database configuration
    # # Example: postgresql+asyncpg://user:password@host:port/db_name
    # DATABASE_URL: str = "postgresql+asyncpg://user:password@localhost:5432/db_name"
    # # ALEMBIC_DATABASE_URL: str 

    # TEST_DATABASE_URL: str | None = None


    # AI Configuration
    # AZURE_OPENAI_ENDPOINT: str
    AZURE_OPENAI_API_KEY: str
    AZURE_OPENAI_MODEL: str = "gpt-35-turbo"
    AZURE_OPENAI_ENDPOINT: str = "https://api.openai.com/v1"
    AZURE_OPENAI_API_BASE: str = "https://api.openai.com/v1"

    AZURE_OPENAI_API_VERSION: str = "2024-12-01-preview"
    AZURE_OPENAI_03_MINI_DEPLOYMENT_NAME: str = "o3-mini"
    AZURE_35_TURBO_DEPLOYMENT_NAME: str = "gpt-35-turbo"



    # REDIS_HOST: str = "localhost"
    # REDIS_PORT: int = 6379
    # REDIS_PASSWORD: Optional[str] = None
    # REDIS_DB: int = 0

      # Kafka settings
    KAFKA_BOOTSTRAP_SERVERS: str # e.g., "kafka-12345-project.aivencloud.com:12345"
    # KAFKA_INCOMING_MESSAGES_TOPIC: str

    # SSL Certificate paths (for client certificate authentication)
    KAFKA_SSL_CAFILE: Optional[str] = None      # Path to CA certificate
    KAFKA_SSL_CERTFILE: Optional[str] = None    # Path to client certificate
    KAFKA_SSL_KEYFILE: Optional[str] = None     # Path to client key

    # SASL Authentication (alternative to certificates)
    KAFKA_USERNAME: Optional[str] = None
    KAFKA_PASSWORD: Optional[str] = None
    KAFKA_SASL_MECHANISM: str = "PLAIN"  # or "SCRAM-SHA-256", "SCRAM-SHA-512"
    
    # Kafka Security Protocol
    KAFKA_SECURITY_PROTOCOL: str = "SSL"  # or "SASL_SSL" if using SASL

    # Redis settings
    REDIS_URL: str

    # MongoDB settings
    MONGO_URL: str
    MONGO_DB_NAME: str

    # # Redis session storage
    # REDIS_SESSION_STORAGE: bool = False
    # USE_REDIS: bool = False

    
    model_config = SettingsConfigDict(env_file=".env")

settings = Settings()