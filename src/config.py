from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_PATH = PROJECT_ROOT / "data"

INCIDENTS_PATH = DATA_PATH / "incidents"
LOGS_PATH = DATA_PATH / "logs"
METRICS_PATH = DATA_PATH / "metrics"
RUNBOOKS_PATH = DATA_PATH / "runbooks"
TRACES_PATH = DATA_PATH / "traces"
DEPLOYMENTS_FILE = DATA_PATH / "deployments.json"
EXTERNAL_RCAEVAL_PATH = DATA_PATH / "external" / "rcaeval"


class Settings(BaseSettings):
    ollama_model: str = "qwen3.5:4b"
    ollama_base_url: str = "http://localhost:11434"
    ollama_reasoning: bool = False
    ollama_num_predict: int = 512
    ollama_keep_alive: str = "30m"
    max_tool_calls: int = 8

    model_config = SettingsConfigDict(env_file=PROJECT_ROOT / ".env", extra="ignore")


settings = Settings()

OLLAMA_MODEL = settings.ollama_model
OLLAMA_BASE_URL = settings.ollama_base_url
OLLAMA_REASONING = settings.ollama_reasoning
OLLAMA_NUM_PREDICT = settings.ollama_num_predict
OLLAMA_KEEP_ALIVE = settings.ollama_keep_alive
MAX_TOOL_CALLS = settings.max_tool_calls
