import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://invariant:invariant@localhost:5432/invariant_core_db"
)
PUBSUB_PROJECT_ID = os.environ.get("PUBSUB_PROJECT_ID", "invariant-local")
PUBSUB_EMULATOR_HOST = os.environ.get("PUBSUB_EMULATOR_HOST", None)

ORDER_SERVICE_URL = os.environ.get("ORDER_SERVICE_URL", "http://localhost:8001")
PAYMENT_SERVICE_URL = os.environ.get("PAYMENT_SERVICE_URL", "http://localhost:8002")
ERP_SERVICE_URL = os.environ.get("ERP_SERVICE_URL", "http://localhost:8003")
SHIPPING_SERVICE_URL = os.environ.get("SHIPPING_SERVICE_URL", "http://localhost:8004")
SIMULATOR_URL = os.environ.get("SIMULATOR_URL", "http://localhost:8000")

