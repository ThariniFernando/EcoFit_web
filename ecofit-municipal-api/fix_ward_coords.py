import os
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv()

client = MongoClient(os.getenv("MONGO_URL"))
db = client[os.getenv("DB_NAME", "ecofit_db")]
col = db[os.getenv("WARDS_MASTER_COL", "wards_master")]

# Manual coordinates for wards Nominatim couldn't find
WARD_COORDS = {
    "KOCHCHIKADE_SOUTH":   {"lat": 6.9433, "lng": 79.8541},
    "WELLAWATTA_NORTH":    {"lat": 6.8952, "lng": 79.8541},
    "KOTAHENA_EAST":       {"lat": 6.9378, "lng": 79.8601},
    "GRANDPASS_SOUTH":     {"lat": 6.9312, "lng": 79.8589},
    "JINTUPITIYA":         {"lat": 6.9448, "lng": 79.8578},
    "BORELLA_NORTH":       {"lat": 6.9178, "lng": 79.8634},
    "WELLAWATTA_SOUTH":    {"lat": 6.8890, "lng": 79.8530},
    "MALIGAWATTA_EAST":    {"lat": 6.9421, "lng": 79.8645},
    "KHETTARAMA":          {"lat": 6.9198, "lng": 79.8712},
    "MALIGAWATTA_WEST":    {"lat": 6.9418, "lng": 79.8601},
    "KOTAHENA_WEST":       {"lat": 6.9356, "lng": 79.8556},
    "HULSTORF_WEST":       {"lat": 6.9478, "lng": 79.8534},
    "PAMANKADA_WEST":      {"lat": 6.8795, "lng": 79.8623},
    "SAMMANTHRANAPURA":    {"lat": 6.9289, "lng": 79.8534},
    "ALUTH_MAWATHA":       {"lat": 6.9389, "lng": 79.8623},
    "NAVAGAMPURA":         {"lat": 6.9312, "lng": 79.8712},
    "HULSTORF_EAST":       {"lat": 6.9489, "lng": 79.8567},
    "PAMANKADA_EAST":      {"lat": 6.8812, "lng": 79.8667},
    "KUPPIYAWATTA_EAST":   {"lat": 6.9234, "lng": 79.8689},
    "KUPPIYAWATTA_WEST":   {"lat": 6.9223, "lng": 79.8656},
    "BORELLA_SOUTH":       {"lat": 6.9134, "lng": 79.8656},
    "KESELWATTA":          {"lat": 6.9389, "lng": 79.8534},
    "GRANDPASS_NORTH":     {"lat": 6.9356, "lng": 79.8623},
    "NEW_BAZAAR":          {"lat": 6.9312, "lng": 79.8534},
    "PANCHIKAWATTA":       {"lat": 6.9267, "lng": 79.8634},
}

updated = 0
not_found = 0

for ward_id, coords in WARD_COORDS.items():
    result = col.update_one(
        {"wardId": ward_id},
        {"$set": {"center": coords}},
    )
    if result.matched_count == 0:
        print(f"NOT IN DB: {ward_id}")
        not_found += 1
    else:
        print(f"UPDATED: {ward_id:30s} -> {coords['lat']}, {coords['lng']}")
        updated += 1

print(f"\n✅ DONE — updated: {updated}  not found in DB: {not_found}")