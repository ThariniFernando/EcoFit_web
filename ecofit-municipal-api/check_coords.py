from pymongo import MongoClient
import os
from dotenv import load_dotenv
from collections import Counter

load_dotenv()

client = MongoClient(os.getenv("MONGO_URL"))
db = client[os.getenv("DB_NAME", "ecofit_db")]

coords = []
for w in db["wards_master"].find({}, {"wardId": 1, "wardName": 1, "center": 1}):
    c = w.get("center") or {}
    lat = round(c.get("lat", 0), 4)
    lng = round(c.get("lng", 0), 4)
    coords.append((lat, lng))
    print(f"{w.get('wardName','?'):30s}  lat={lat}  lng={lng}")

dupes = {k: v for k, v in Counter(coords).items() if v > 1}
print("\nDuplicate coordinates:", dupes)
print("Total wards:", len(coords))