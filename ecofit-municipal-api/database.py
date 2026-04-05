from motor.motor_asyncio import AsyncIOMotorClient
from config import MONGO_URL, DB_NAME, MONGO_URL_SECONDARY, DB_NAME_SECONDARY

client = AsyncIOMotorClient(MONGO_URL)
secondary_client = AsyncIOMotorClient(MONGO_URL_SECONDARY)

database = client[DB_NAME]
secondary_database = secondary_client[DB_NAME_SECONDARY]