import os
from dotenv import load_dotenv

load_dotenv()

ORDER_URL    = os.environ.get("ORDER_SERVICE_URL",    "http://localhost:8001")
PAYMENT_URL  = os.environ.get("PAYMENT_SERVICE_URL",  "http://localhost:8002")
ERP_URL      = os.environ.get("ERP_SERVICE_URL",      "http://localhost:8003")
SHIPPING_URL = os.environ.get("SHIPPING_SERVICE_URL", "http://localhost:8004")

