import os
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv

# Load .env explicitly from the same directory as this file
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), ".env"))

MONGO_URL = os.getenv("MONGO_URL")
DB_NAME   = os.getenv("DB_NAME")

if not MONGO_URL:
    raise RuntimeError("MONGO_URL is not set — check your .env file")

client   = AsyncIOMotorClient(MONGO_URL)
database = client[DB_NAME]