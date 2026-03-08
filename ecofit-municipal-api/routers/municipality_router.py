from fastapi import APIRouter, HTTPException
from database import database
from models.municipality_model import MunicipalityCreate
from bson import ObjectId

router = APIRouter(
    prefix="/municipalities",
    tags=["Municipalities"]
)

municipality_collection = database.get_collection("municipalities")


@router.post("/")
async def create_municipality(data: MunicipalityCreate):
    result = await municipality_collection.insert_one(data.dict())
    return {"id": str(result.inserted_id)}


@router.get("/")
async def get_municipalities():
    municipalities = []
    async for doc in municipality_collection.find():
        doc["id"] = str(doc["_id"])
        del doc["_id"]
        municipalities.append(doc)
    return municipalities


@router.get("/{id}")
async def get_municipality(id: str):
    municipality = await municipality_collection.find_one(
        {"_id": ObjectId(id)}
    )
    if not municipality:
        raise HTTPException(status_code=404, detail="Not found")

    municipality["id"] = str(municipality["_id"])
    del municipality["_id"]
    return municipality


@router.put("/{id}")
async def update_municipality(id: str, data: MunicipalityCreate):
    result = await municipality_collection.update_one(
        {"_id": ObjectId(id)},
        {"$set": data.dict()}
    )
    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="Not updated")
    return {"message": "Updated successfully"}


@router.delete("/{id}")
async def delete_municipality(id: str):
    await municipality_collection.delete_one({"_id": ObjectId(id)})
    return {"message": "Deleted successfully"}