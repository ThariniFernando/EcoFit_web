from pydantic import BaseModel
from pydantic import ConfigDict


class MunicipalityBase(BaseModel):
    name: str
    district: str
    state: str


class MunicipalityCreate(MunicipalityBase):
    pass


class MunicipalityResponse(MunicipalityBase):
    id: str

    model_config = ConfigDict(from_attributes=True)