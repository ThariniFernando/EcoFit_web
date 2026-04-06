import os
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List

import pandas as pd
from dotenv import load_dotenv
from pymongo import UpdateOne

from database import database

load_dotenv()

SERVICE_LOGS_COL = os.getenv("SERVICE_LOGS_COL", "service_logs")
COMPLAINTS_COL   = os.getenv("COMPLAINTS_COL", "complaints")
WEATHER_COL      = os.getenv("WEATHER_COL", "weather_hourly")
WARD_FEATURES_COL = os.getenv("WARD_FEATURES_COL", "ward_hourly_features")

# FIX: prevent loading entire collection into memory
MAX_DOCS = int(os.getenv("FEATURES_MAX_DOCS", "100000"))


def to_dt(x: Any):
    if x is None:
        return None
    if isinstance(x, datetime):
        return x if x.tzinfo else x.replace(tzinfo=timezone.utc)
    try:
        return datetime.fromisoformat(str(x).replace("Z", "+00:00"))
    except Exception:
        return None


def hour_floor(dt: datetime) -> datetime:
    return dt.replace(minute=0, second=0, microsecond=0)


def extract_ward_id(doc: Dict[str, Any]):
    for k in ["wardId", "ward_id"]:
        if doc.get(k):
            return str(doc[k]).strip()
    w = doc.get("ward")
    if isinstance(w, dict):
        for k in ["wardId", "ward_id", "id", "name", "wardName", "ward_name", "code"]:
            if w.get(k):
                return str(w[k]).strip()
    if doc.get("wardName"):
        return str(doc["wardName"]).strip()
    return None


def safe_int(x: Any, default: int = 0) -> int:
    try:
        return default if x is None else int(x)
    except Exception:
        return default


def safe_float(x: Any, default: float = 0.0) -> float:
    try:
        return default if x is None else float(x)
    except Exception:
        return default


async def build_hourly_features_df(start: datetime, end: datetime) -> pd.DataFrame:
    # FIX: bounded to_list
    service_docs = await database[SERVICE_LOGS_COL].find(
        {"createdAt": {"$gte": start, "$lt": end}},
        projection={
            "_id": 0, "createdAt": 1, "wardId": 1, "ward": 1,
            "outcome": 1, "result": 1, "status": 1,
            "estimatedKg": 1, "binsCleared": 1,
        },
    ).to_list(length=MAX_DOCS)

    s_rows: List[Dict[str, Any]] = []
    for d in service_docs:
        dt = to_dt(d.get("createdAt"))
        if not dt:
            continue
        wid = extract_ward_id(d)
        if not wid:
            continue
        outcome = (d.get("outcome") or d.get("result") or d.get("status") or "").upper().strip()
        s_rows.append({
            "tsHour": hour_floor(dt),
            "wardId": wid,
            "serviceCollected": 1 if "COLLECT" in outcome else 0,
            "serviceMissed":    1 if "MISS"    in outcome else 0,
            "servicePartial":   1 if "PART"    in outcome else 0,
            "estimatedKg": safe_float(d.get("estimatedKg")),
            "binsCleared":  safe_int(d.get("binsCleared")),
        })

    service_df = pd.DataFrame(s_rows)
    service_agg = (
        service_df.groupby(["tsHour", "wardId"], as_index=False).agg(
            serviceCollected=("serviceCollected", "sum"),
            serviceMissed=("serviceMissed", "sum"),
            servicePartial=("servicePartial", "sum"),
            estimatedKg=("estimatedKg", "sum"),
            binsCleared=("binsCleared", "sum"),
        ) if not service_df.empty else pd.DataFrame(columns=["tsHour", "wardId"])
    )

    # FIX: bounded to_list
    complaint_docs = await database[COMPLAINTS_COL].find(
        {"createdAt": {"$gte": start, "$lt": end}},
        projection={
            "_id": 0, "createdAt": 1, "wardId": 1, "ward": 1,
            "severity": 1, "status": 1, "category": 1,
        },
    ).to_list(length=MAX_DOCS)

    c_rows: List[Dict[str, Any]] = []
    for d in complaint_docs:
        dt = to_dt(d.get("createdAt"))
        if not dt:
            continue
        wid = extract_ward_id(d)
        if not wid:
            continue
        sev      = safe_float(d.get("severity"))
        status   = str(d.get("status")   or "").upper().strip()
        category = str(d.get("category") or "").upper().strip()
        c_rows.append({
            "tsHour": hour_floor(dt),
            "wardId": wid,
            "complaintsCount":      1,
            "unresolvedComplaints": 0 if status in ["RESOLVED", "CLOSED"] else 1,
            "overflowPoints":       1 if category in ["OVERFLOW", "OVERFLOWING"] else 0,
            "avgSeverity":          sev,
        })

    complaints_df = pd.DataFrame(c_rows)
    if complaints_df.empty:
        complaints_agg = pd.DataFrame(columns=["tsHour", "wardId"])
    else:
        complaints_agg = complaints_df.groupby(["tsHour", "wardId"], as_index=False).agg(
            complaintsCount=("complaintsCount", "sum"),
            unresolvedComplaints=("unresolvedComplaints", "sum"),
            overflowPoints=("overflowPoints", "sum"),
            avgSeverity=("avgSeverity", "mean"),
        )

    base = pd.merge(service_agg, complaints_agg, on=["tsHour", "wardId"], how="outer")

    for col in [
        "serviceCollected", "serviceMissed", "servicePartial",
        "estimatedKg", "binsCleared",
        "complaintsCount", "unresolvedComplaints", "overflowPoints", "avgSeverity",
    ]:
        if col not in base.columns:
            base[col] = 0
        base[col] = base[col].fillna(0)

    # FIX: bounded to_list
    weather_docs = await database[WEATHER_COL].find(
        {"tsHour": {"$gte": start, "$lt": end}},
        projection={
            "_id": 0, "tsHour": 1, "tempC": 1, "rainMm": 1,
            "windKph": 1, "precipMm": 1, "precipProb": 1,
        },
    ).to_list(length=MAX_DOCS)

    w_rows = []
    for d in weather_docs:
        dt = to_dt(d.get("tsHour"))
        if not dt:
            continue
        w_rows.append({
            "tsHour":     hour_floor(dt),
            "tempC":      safe_float(d.get("tempC")),
            "rainMm":     safe_float(d.get("rainMm")),
            "windKph":    safe_float(d.get("windKph")),
            "precipMm":   safe_float(d.get("precipMm")),
            "precipProb": safe_float(d.get("precipProb")),
        })

    weather_df = (
        pd.DataFrame(w_rows).drop_duplicates(subset=["tsHour"])
        if w_rows else pd.DataFrame(columns=["tsHour"])
    )

    if not weather_df.empty:
        base = pd.merge(base, weather_df, on="tsHour", how="left")

    for col in ["tempC", "rainMm", "windKph", "precipMm", "precipProb"]:
        if col not in base.columns:
            base[col] = 0.0
        base[col] = base[col].fillna(0.0)

    if base.empty:
        return base

    base["tsHour"]    = pd.to_datetime(base["tsHour"], utc=True)
    base["hour"]      = base["tsHour"].dt.hour
    base["dayOfWeek"] = base["tsHour"].dt.dayofweek

    return base.sort_values(["wardId", "tsHour"]).reset_index(drop=True)


async def rebuild_recent_ward_hourly_features(hours_back: int = 240):
    end   = datetime.now(timezone.utc)
    start = end - timedelta(hours=hours_back)

    df = await build_hourly_features_df(start, end)

    if df.empty:
        return {"ok": True, "rows": 0, "collection": WARD_FEATURES_COL}

    ops = []
    now = datetime.now(timezone.utc)

    for _, row in df.iterrows():
        doc = {
            "wardId":               row["wardId"],
            "tsHour":               row["tsHour"].to_pydatetime(),
            "serviceCollected":     int(row.get("serviceCollected", 0)),
            "serviceMissed":        int(row.get("serviceMissed", 0)),
            "servicePartial":       int(row.get("servicePartial", 0)),
            "estimatedKg":          float(row.get("estimatedKg", 0.0)),
            "binsCleared":          int(row.get("binsCleared", 0)),
            "complaintsCount":      int(row.get("complaintsCount", 0)),
            "unresolvedComplaints": int(row.get("unresolvedComplaints", 0)),
            "overflowPoints":       int(row.get("overflowPoints", 0)),
            "avgSeverity":          float(row.get("avgSeverity", 0.0)),
            "tempC":                float(row.get("tempC", 0.0)),
            "rainMm":               float(row.get("rainMm", 0.0)),
            "windKph":              float(row.get("windKph", 0.0)),
            "precipMm":             float(row.get("precipMm", 0.0)),
            "precipProb":           float(row.get("precipProb", 0.0)),
            "hour":                 int(row.get("hour", 0)),
            "dayOfWeek":            int(row.get("dayOfWeek", 0)),
            "updatedAt":            now,
        }
        ops.append(UpdateOne(
            {"wardId": doc["wardId"], "tsHour": doc["tsHour"]},
            {"$set": doc},
            upsert=True,
        ))

    if ops:
        await database[WARD_FEATURES_COL].bulk_write(ops)

    return {"ok": True, "rows": len(ops), "collection": WARD_FEATURES_COL}