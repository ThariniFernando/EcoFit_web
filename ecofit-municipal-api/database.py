import os
from motor.motor_asyncio import AsyncIOMotorClient
from config import MONGO_URL, DB_NAME, MONGO_URL_SECONDARY, DB_NAME_SECONDARY
from dotenv import load_dotenv


client = AsyncIOMotorClient(MONGO_URL)
secondary_client = AsyncIOMotorClient(MONGO_URL_SECONDARY)

database = client[DB_NAME]
secondary_database = secondary_client[DB_NAME_SECONDARY]

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), ".env"))

MONGO_URL = os.getenv("MONGO_URL")
DB_NAME   = os.getenv("DB_NAME")

if not MONGO_URL:
    raise RuntimeError("MONGO_URL is not set — check your .env file")

client   = AsyncIOMotorClient(MONGO_URL)
database = client[DB_NAME]
