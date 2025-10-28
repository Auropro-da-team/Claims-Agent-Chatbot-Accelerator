import os
from dotenv import load_dotenv

# Load environment variables from a .env file for local development
load_dotenv()

# -------------------------
# CONFIGURATION
# -------------------------
# Load sensitive configuration from environment variables.
# The application will NOT start if these are not set.
PROJECT_ID = os.getenv("PROJECT_ID")
REGION = os.getenv("REGION")
INDEX_ENDPOINT_ID = os.getenv("INDEX_ENDPOINT_ID")
DEPLOYED_INDEX_ID = os.getenv("DEPLOYED_INDEX_ID")
BUCKET_NAME = os.getenv("BUCKET_NAME")

# --- Configuration Validation ---
# Ensure all required environment variables are set.
required_configs = {
    "PROJECT_ID": PROJECT_ID,
    "REGION": REGION,
    "INDEX_ENDPOINT_ID": INDEX_ENDPOINT_ID,
    "DEPLOYED_INDEX_ID": DEPLOYED_INDEX_ID,
    "BUCKET_NAME": BUCKET_NAME
}

missing_configs = [key for key, value in required_configs.items() if value is None]
if missing_configs:
    raise ValueError(f"Missing required environment variables: {', '.join(missing_configs)}")
