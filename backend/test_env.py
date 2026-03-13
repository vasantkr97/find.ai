import os
from dotenv import load_dotenv

load_dotenv()

from app.core.config import get_settings

print("ENV GOOGLE_CLIENT_ID:", os.getenv("GOOGLE_CLIENT_ID"))

try:
    settings = get_settings()
    print("SETTINGS GOOGLE_CLIENT_ID:", settings.GOOGLE_CLIENT_ID)
except Exception as e:
    print("Error loading settings:", e)
