from pydantic import BaseModel, Field
from typing import Optional
from bson import ObjectId

class PyObjectId(ObjectId):
    @classmethod
    def __get_validators__(cls):
        yield cls.validate

    @classmethod
    def validate(cls, v):
        if not ObjectId.is_valid(v):
            raise ValueError("Invalid object id")
        return ObjectId(v)

class MunicipalityBase(BaseModel):
    name: str
    district: str
    state: str

class MunicipalityCreate(MunicipalityBase):
    pass

class MunicipalityResponse(MunicipalityBase):
    id: str

    class Config:
        orm_mode = True