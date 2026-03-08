import os
import time
from typing import Any, Dict, Optional, Tuple

import requests
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv()

MONGO_URL = os.getenv("MONGO_URL")
DB_NAME = os.getenv("DB_NAME", "ecofit_db")
WARDS_MASTER_COL = os.getenv("WARDS_MASTER_COL", "wards_master")

# Put a real email in .env to avoid Nominatim blocking you
NOMINATIM_EMAIL = os.getenv("NOMINATIM_EMAIL", "your_email@example.com")
USER_AGENT = f"EcoFitMunicipal/1.0 ({NOMINATIM_EMAIL})"

# Colombo rough bounding box (land area)
# If coordinate is outside this, we consider it "wrong"
COLOMBO_BOX = {
    "min_lat": 6.75,
    "max_lat": 7.10,
    "min_lng": 79.78,
    "max_lng": 79.95,
}


def get_db():
    if not MONGO_URL:
        raise RuntimeError("❌ MONGO_URL missing in .env")
    client = MongoClient(MONGO_URL)
    return client[DB_NAME]


def to_float(x: Any) -> Optional[float]:
    try:
        if x is None:
            return None
        return float(x)
    except Exception:
        return None


def in_colombo_box(lat: float, lng: float) -> bool:
    return (
        COLOMBO_BOX["min_lat"] <= lat <= COLOMBO_BOX["max_lat"]
        and COLOMBO_BOX["min_lng"] <= lng <= COLOMBO_BOX["max_lng"]
    )


def geocode_place(session: requests.Session, q: str) -> Optional[Tuple[float, float]]:
    url = "https://nominatim.openstreetmap.org/search"
    params = {"q": q, "format": "json", "limit": 1}

    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "application/json",
    }

    r = session.get(url, params=params, headers=headers, timeout=20)

    if r.status_code != 200:
        # show some error body to debug
        print("Nominatim response:", r.status_code, r.text[:200])
        r.raise_for_status()

    data = r.json()
    if not data:
        return None

    lat = float(data[0]["lat"])
    lng = float(data[0]["lon"])
    return lat, lng


def detect_all_same_center(wards: list) -> bool:
    pts = []
    for w in wards:
        c = w.get("center") or {}
        lat = to_float(c.get("lat")) if isinstance(c, dict) else None
        lng = to_float(c.get("lng")) if isinstance(c, dict) else None
        if lat is not None and lng is not None:
            pts.append((round(lat, 6), round(lng, 6)))

    if len(pts) <= 1:
        return False
    return len(set(pts)) == 1


def should_update_center(w: Dict[str, Any], force_all_same: bool) -> bool:
    """
    Update if:
    - missing lat/lng
    - or outside Colombo box
    - or (special) all wards share the same center => update all
    """
    if force_all_same:
        return True

    c = w.get("center") or {}
    if not isinstance(c, dict):
        return True

    lat = to_float(c.get("lat"))
    lng = to_float(c.get("lng"))

    if lat is None or lng is None:
        return True

    if not in_colombo_box(lat, lng):
        return True

    return False


def main():
    db = get_db()
    col = db[WARDS_MASTER_COL]

    wards = list(
        col.find(
            {"active": True},
            projection={"_id": 1, "wardId": 1, "wardName": 1, "center": 1, "active": 1},
        )
    )

    if not wards:
        print("❌ No active wards found.")
        return

    # If all wards share one same coordinate => update ALL
    force_all_same = detect_all_same_center(wards)
    if force_all_same:
        print("⚠️ Detected: All wards share the same center. Will update ALL wards.")

    session = requests.Session()

    updated = 0
    skipped = 0
    failed = 0

    for w in wards:
        ward_id = (w.get("wardId") or "").strip()
        ward_name = (w.get("wardName") or "").strip()

        if not ward_id:
            skipped += 1
            continue

        if not should_update_center(w, force_all_same):
            skipped += 1
            continue

        # Query built from wardName; if missing use wardId
        query = f"{ward_name}, Colombo, Sri Lanka" if ward_name else f"{ward_id.replace('_', ' ')}, Colombo, Sri Lanka"

        try:
            # IMPORTANT: be polite to Nominatim
            time.sleep(1.1)

            result = geocode_place(session, query)
            if not result:
                print(f"NOT FOUND: {ward_id} {ward_name} -> {query}")
                failed += 1
                continue

            lat, lng = result

            col.update_one(
                {"_id": w["_id"]},
                {"$set": {"center": {"lat": lat, "lng": lng}}},
            )

            updated += 1
            print(f"UPDATED: {ward_id} | {ward_name} -> {lat}, {lng}")

        except Exception as e:
            failed += 1
            print(f"ERROR: {ward_id} | {ward_name} -> {e}")

    print("\n✅ DONE")
    print("updated:", updated, "skipped:", skipped, "failed:", failed)


if __name__ == "__main__":
    main()