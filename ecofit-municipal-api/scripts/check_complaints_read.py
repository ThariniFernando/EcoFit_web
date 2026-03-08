import os
import asyncio
from motor.motor_asyncio import AsyncIOMotorClient

MONGO_URL = os.getenv("mongodb+srv://Pawani:ecofit123@cluster0.zg0jvo4.mongodb.net/?appName=Cluster0")
DB_NAME = os.getenv("ecofit_db", "ecofit_db")

async def main():
    if not MONGO_URL:
        raise RuntimeError("MONGO_URL not set in environment/.env")

    client = AsyncIOMotorClient(MONGO_URL)
    db = client[DB_NAME]

    coll = db["complaints"]

    total = await coll.count_documents({})
    sample = await coll.find_one({})

    print("DB_NAME:", DB_NAME)
    print("Total complaints:", total)
    print("Sample keys:", list(sample.keys()) if sample else None)

    client.close()

if __name__ == "__main__":
    asyncio.run(main())