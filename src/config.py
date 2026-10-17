from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_PATH = PROJECT_ROOT / "data"

LOGS_PATH = DATA_PATH / "logs"
METRICS_PATH = DATA_PATH / "metrics"
RUNBOOKS_PATH = DATA_PATH / "runbooks"
DEPLOYMENTS_FILE = DATA_PATH / "deployments.json"