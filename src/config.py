from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_PATH = PROJECT_ROOT / "data"

INCIDENTS_PATH = DATA_PATH / "incidents"
LOGS_PATH = DATA_PATH / "logs"
METRICS_PATH = DATA_PATH / "metrics"
RUNBOOKS_PATH = DATA_PATH / "runbooks"
DEPLOYMENTS_FILE = DATA_PATH / "deployments.json"


class Settings(BaseSettings):
    ollama_model: str = "qwen3.5:4b"
    ollama_base_url: str = "http://localhost:11434"
    max_tool_calls: int = 8

    model_config = SettingsConfigDict(env_file=PROJECT_ROOT / ".env", extra="ignore")


settings = Settings()

OLLAMA_MODEL = settings.ollama_model
OLLAMA_BASE_URL = settings.ollama_base_url
MAX_TOOL_CALLS = settings.max_tool_calls
