import os
from motor.motor_asyncio import AsyncIOMotorClient
from config import MONGO_URL, DB_NAME, MONGO_URL_SECONDARY, DB_NAME_SECONDARY

# Validate required env vars before any connection attempt
if not MONGO_URL:
    raise RuntimeError("MONGO_URL is not set — check your environment variables or .env file")
if not DB_NAME:
    raise RuntimeError("DB_NAME is not set — check your environment variables or .env file")
if not MONGO_URL_SECONDARY:
    raise RuntimeError("MONGO_URL_SECONDARY is not set — check your environment variables or .env file")
if not DB_NAME_SECONDARY:
    raise RuntimeError("DB_NAME_SECONDARY is not set — check your environment variables or .env file")

# Primary database
client = AsyncIOMotorClient(MONGO_URL)
database = client[DB_NAME]

# Secondary database (separate real connection)
secondary_client = AsyncIOMotorClient(MONGO_URL_SECONDARY)
secondary_database = secondary_client[DB_NAME_SECONDARY]