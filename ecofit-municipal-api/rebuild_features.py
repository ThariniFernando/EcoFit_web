import asyncio
import os
from dotenv import load_dotenv

load_dotenv()

async def main():
    from database import database
    from services.ward_features_builder import rebuild_recent_ward_hourly_features
    # Pull 720 hours (30 days) instead of 240
    result = await rebuild_recent_ward_hourly_features(hours_back=720)
    print("Features rebuilt:", result)

asyncio.run(main())