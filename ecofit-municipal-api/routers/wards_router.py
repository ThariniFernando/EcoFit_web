from fastapi import APIRouter
from database import database

router = APIRouter(prefix="/api/v1/wards", tags=["Wards"])

@router.get("")
async def get_wards():
    cursor = database["wards_master"].find({}, {"_id": 0, "wardId": 1, "wardName": 1, "wardNo": 1, "center": 1})
    wards = await cursor.to_list(length=1000)
    # sort by wardNo if available
    wards.sort(key=lambda w: w.get("wardNo", 9999))
    return wards