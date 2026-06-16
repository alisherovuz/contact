import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_IDS_STR = os.getenv("ADMIN_IDS")

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN is missing in the environment variables.")

if not ADMIN_IDS_STR:
    raise ValueError("ADMIN_IDS is missing in the environment variables. Provide comma-separated integer user IDs.")

# Ensure ADMIN_IDS are converted to integers
try:
    ADMIN_IDS = [int(admin_id.strip()) for admin_id in ADMIN_IDS_STR.split(",") if admin_id.strip()]
except ValueError:
    raise ValueError("ADMIN_IDS must contain valid comma-separated integers.")

