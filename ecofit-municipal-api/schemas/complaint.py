from pydantic import BaseModel, Field
from typing import Optional, List, Literal, Any, Dict
from datetime import datetime

# ✅ Match your DB values (you showed "NEW")
ComplaintStatus = Literal["NEW", "IN_PROGRESS", "RESOLVED", "REJECTED"]


class WardInfo(BaseModel):
    wardId: Optional[str] = None
    wardName: Optional[str] = None
    wardNo: Optional[int] = None
    center: Optional[Dict[str, Any]] = None  # keep flexible (lat/lng)


class LocationInfo(BaseModel):
    address: Optional[str] = None
    lat: Optional[float] = None
    lng: Optional[float] = None
    extra: Optional[Dict[str, Any]] = None  # keep flexible


class StatusHistoryItem(BaseModel):
    status: Optional[str] = None
    at: Optional[datetime] = None
    by: Optional[str] = None
    note: Optional[str] = None
    extra: Optional[Dict[str, Any]] = None


class ComplaintOut(BaseModel):
    id: str = Field(..., description="Mongo ObjectId as string")

    complaintId: Optional[str] = None
    source: Optional[str] = None

    ward: Optional[WardInfo] = None
    location: Optional[LocationInfo] = None

    category: Optional[str] = None
    severity: Optional[int] = None
    description: Optional[str] = None

    status: ComplaintStatus = "NEW"
    statusHistory: Optional[List[StatusHistoryItem]] = None

    assignedTo: Optional[Any] = None
    resolvedAt: Optional[datetime] = None
    resolution: Optional[str] = None

    createdAt: Optional[datetime] = None
    updatedAt: Optional[datetime] = None

    # keep any other mobile fields without breaking
    extra: Optional[Dict[str, Any]] = None


class ComplaintListResponse(BaseModel):
    items: List[ComplaintOut]
    total: int


class ComplaintStatusUpdateIn(BaseModel):
    status: ComplaintStatus
    note: Optional[str] = None  # optional reason/comment when updating status