import os
from pydantic_settings import BaseSettings
from dotenv import load_dotenv

# Load .env file explicitly to ensure it works even if not in CWD
load_dotenv()

class Settings(BaseSettings):
    discord_token: str
    mongo_uri: str
    db_name: str = "OP_SHOP_TEST"
    owner_id: int
    openai_api_key: str

    class Config:
        env_file = ".env"
        case_sensitive = False

# Global settings instance
try:
    settings = Settings()
except Exception as e:
    print(f"Error loading settings: {e}")
    # Fallback or exit if critical env vars are missing
    raise
