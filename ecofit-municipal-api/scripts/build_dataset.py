import os
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, Optional

import pandas as pd
from dotenv import load_dotenv
from pymongo import MongoClient

# =========================
# CONFIG
# =========================
load_dotenv()

MONGO_URL = os.getenv("MONGO_URL")
DB_NAME = os.getenv("DB_NAME", "ecofit_db")

SERVICE_LOGS_COL = os.getenv("SERVICE_LOGS_COL", "service_logs")
COMPLAINTS_COL = os.getenv("COMPLAINTS_COL", "complaints")
WEATHER_COL = os.getenv("WEATHER_COL", "weather_hourly")  # global weather (no wardId)

OUT_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
os.makedirs(OUT_DIR, exist_ok=True)
OUT_CSV = os.path.join(OUT_DIR, "ward_timeseries_hourly.csv")

# Standard setup (override via .env if you want)
HISTORY_HOURS = int(os.getenv("HISTORY_HOURS", "168"))     # 7 days
HORIZON_HOURS = int(os.getenv("HORIZON_HOURS", "24"))      # next 24h
LOOKBACK_DAYS = int(os.getenv("DATASET_LOOKBACK_DAYS", "60"))

# =========================
# HELPERS
# =========================
def to_dt(x: Any) -> Optional[datetime]:
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

def extract_ward_id(doc: Dict[str, Any]) -> Optional[str]:
    # top-level
    for k in ["wardId", "ward_id"]:
        if doc.get(k):
            return str(doc[k]).strip()

    # nested ward object
    w = doc.get("ward")
    if isinstance(w, dict):
        for k in ["wardId", "ward_id", "id", "name", "wardName", "ward_name", "code"]:
            if w.get(k):
                return str(w[k]).strip()

    # fallback
    if doc.get("wardName"):
        return str(doc["wardName"]).strip()

    return None

def safe_int(x: Any, default: int = 0) -> int:
    try:
        if x is None:
            return default
        return int(x)
    except Exception:
        return default

def safe_float(x: Any, default: float = 0.0) -> float:
    try:
        if x is None:
            return default
        return float(x)
    except Exception:
        return default

# =========================
# 1) BUILD SPARSE HOURLY FEATURES (only hours with events)
# =========================
def build_hourly_sparse(db, start: datetime, end: datetime) -> pd.DataFrame:
    # ---- service logs ----
    service_docs = list(
        db[SERVICE_LOGS_COL].find(
            {"createdAt": {"$gte": start, "$lt": end}},
            projection={
                "_id": 0,
                "createdAt": 1,
                "wardId": 1,
                "ward": 1,
                "outcome": 1,
                "result": 1,
                "status": 1,
                "estimatedKg": 1,
                "binsCleared": 1,
            },
        )
    )

    s_rows = []
    for d in service_docs:
        dt = to_dt(d.get("createdAt"))
        if not dt:
            continue
        wid = extract_ward_id(d)
        if not wid:
            continue

        outcome = (d.get("outcome") or d.get("result") or d.get("status") or "").upper().strip()

        s_rows.append(
            {
                "tsHour": hour_floor(dt),
                "wardId": wid,
                "serviceCollected": 1 if "COLLECT" in outcome else 0,
                "serviceMissed": 1 if "MISS" in outcome else 0,
                "servicePartial": 1 if "PART" in outcome else 0,
                "estimatedKg": safe_float(d.get("estimatedKg"), 0.0),
                "binsCleared": safe_int(d.get("binsCleared"), 0),
            }
        )

    service_df = pd.DataFrame(s_rows)
    if service_df.empty:
        service_agg = pd.DataFrame(columns=["tsHour", "wardId"])
    else:
        service_agg = (
            service_df.groupby(["tsHour", "wardId"], as_index=False)
            .agg(
                serviceCollected=("serviceCollected", "sum"),
                serviceMissed=("serviceMissed", "sum"),
                servicePartial=("servicePartial", "sum"),
                estimatedKg=("estimatedKg", "sum"),
                binsCleared=("binsCleared", "sum"),
            )
        )

    # ---- complaints ----
    complaint_docs = list(
        db[COMPLAINTS_COL].find(
            {"createdAt": {"$gte": start, "$lt": end}},
            projection={"_id": 0, "createdAt": 1, "wardId": 1, "ward": 1, "severity": 1, "status": 1, "category": 1},
        )
    )

    c_rows = []
    for d in complaint_docs:
        dt = to_dt(d.get("createdAt"))
        if not dt:
            continue
        wid = extract_ward_id(d)
        if not wid:
            continue

        sev = safe_float(d.get("severity"), 0.0)
        status = str(d.get("status") or "").upper().strip()
        category = str(d.get("category") or "").upper().strip()

        c_rows.append(
            {
                "tsHour": hour_floor(dt),
                "wardId": wid,
                "complaintsCount": 1,
                "severitySum": sev,
                "unresolvedComplaints": 0 if status in ["RESOLVED", "CLOSED"] else 1,
                "overflowPoints": 1 if category in ["OVERFLOW", "OVERFLOWING"] else 0,
            }
        )

    complaints_df = pd.DataFrame(c_rows)
    if complaints_df.empty:
        complaints_agg = pd.DataFrame(columns=["tsHour", "wardId"])
    else:
        complaints_agg = (
            complaints_df.groupby(["tsHour", "wardId"], as_index=False)
            .agg(
                complaintsCount=("complaintsCount", "sum"),
                unresolvedComplaints=("unresolvedComplaints", "sum"),
                overflowPoints=("overflowPoints", "sum"),
                severitySum=("severitySum", "sum"),
            )
        )
        complaints_agg["avgSeverity"] = complaints_agg.apply(
            lambda r: (r["severitySum"] / r["complaintsCount"]) if r["complaintsCount"] > 0 else 0.0, axis=1
        )
        complaints_agg.drop(columns=["severitySum"], inplace=True)

    # ---- merge service + complaints ----
    base = pd.merge(service_agg, complaints_agg, on=["tsHour", "wardId"], how="outer")

    # Fill missing numeric columns with 0
    num_cols = [
        "serviceCollected", "serviceMissed", "servicePartial",
        "estimatedKg", "binsCleared",
        "complaintsCount", "unresolvedComplaints", "overflowPoints", "avgSeverity",
    ]
    for col in num_cols:
        if col not in base.columns:
            base[col] = 0
        base[col] = base[col].fillna(0)

    # ---- global weather join on tsHour ----
    weather_docs = list(
        db[WEATHER_COL].find(
            {"tsHour": {"$gte": start, "$lt": end}},
            projection={"_id": 0, "tsHour": 1, "tempC": 1, "rainMm": 1, "windKph": 1, "precipMm": 1, "precipProb": 1},
        )
    )

    w_rows = []
    for d in weather_docs:
        dt = to_dt(d.get("tsHour"))
        if not dt:
            continue
        w_rows.append(
            {
                "tsHour": hour_floor(dt),
                "tempC": safe_float(d.get("tempC"), 0.0),
                "rainMm": safe_float(d.get("rainMm"), 0.0),
                "windKph": safe_float(d.get("windKph"), 0.0),
                "precipMm": safe_float(d.get("precipMm"), 0.0),
                "precipProb": safe_float(d.get("precipProb"), 0.0),
            }
        )

    weather_df = pd.DataFrame(w_rows).drop_duplicates(subset=["tsHour"]) if w_rows else pd.DataFrame(columns=["tsHour"])

    if not weather_df.empty:
        base = pd.merge(base, weather_df, on="tsHour", how="left")
    else:
        for col in ["tempC", "rainMm", "windKph", "precipMm", "precipProb"]:
            base[col] = 0.0

    for col in ["tempC", "rainMm", "windKph", "precipMm", "precipProb"]:
        if col not in base.columns:
            base[col] = 0.0
        base[col] = base[col].fillna(0.0)

    base["tsHour"] = pd.to_datetime(base["tsHour"], utc=True)
    base = base.sort_values(["wardId", "tsHour"]).reset_index(drop=True)
    return base

# =========================
# 2) MAKE CONTINUOUS HOURLY SERIES (fill missing hours with 0)
# =========================
def make_continuous(df_sparse: pd.DataFrame) -> pd.DataFrame:
    if df_sparse.empty:
        return df_sparse

    min_t = df_sparse["tsHour"].min()
    max_t = df_sparse["tsHour"].max()

    full_time = pd.date_range(start=min_t, end=max_t, freq="h", tz="UTC")
    wards = sorted(df_sparse["wardId"].dropna().unique().tolist())

    feature_cols = [c for c in df_sparse.columns if c not in ["wardId", "tsHour"]]

    out = []
    for wid in wards:
        sub = df_sparse[df_sparse["wardId"] == wid].set_index("tsHour").sort_index()
        sub = sub.reindex(full_time)
        sub["wardId"] = wid
        sub.index.name = "tsHour"
        sub = sub.reset_index()

        for c in feature_cols:
            if c not in sub.columns:
                sub[c] = 0
            sub[c] = sub[c].fillna(0)

        out.append(sub)

    df_full = pd.concat(out, ignore_index=True)
    df_full = df_full.sort_values(["wardId", "tsHour"]).reset_index(drop=True)
    return df_full

# =========================
# 3) FUTURE 24H SCORE + PERCENTILE LABELS (balanced 4-class)
# =========================
def compute_next24_label(df: pd.DataFrame) -> pd.DataFrame:
    df = df.sort_values(["wardId", "tsHour"]).reset_index(drop=True).copy()

    def future_sum(s: pd.Series) -> pd.Series:
        return s.shift(-1).rolling(window=HORIZON_HOURS, min_periods=1).sum()

    df["f_complaints_24h"] = df.groupby("wardId")["complaintsCount"].transform(future_sum)
    df["f_unresolved_24h"] = df.groupby("wardId")["unresolvedComplaints"].transform(future_sum)
    df["f_missed_24h"] = df.groupby("wardId")["serviceMissed"].transform(future_sum)
    df["f_overflow_24h"] = df.groupby("wardId")["overflowPoints"].transform(future_sum)
    df["f_estKg_24h"] = df.groupby("wardId")["estimatedKg"].transform(future_sum)

    # future demand score (continuous)
    df["futureDemandScore"] = (
        2.0 * df["f_overflow_24h"]
        + 1.5 * df["f_missed_24h"]
        + 1.0 * df["f_unresolved_24h"]
        + 0.5 * df["f_complaints_24h"]
        + 0.001 * df["f_estKg_24h"]
    ).fillna(0.0)

    # ✅ Ward-wise percentile labels (guarantees all 4 classes exist)
    parts = []
    for wid, g in df.groupby("wardId", sort=False):
        g = g.copy()
        s = g["futureDemandScore"]

        q50 = s.quantile(0.50)
        q80 = s.quantile(0.80)
        q95 = s.quantile(0.95)

        def cls(v: float) -> str:
            if v >= q95:
                return "EMERGENCY"
            if v >= q80:
                return "HIGH"
            if v >= q50:
                return "MEDIUM"
            return "LOW"

        g["riskClassNext24h"] = s.apply(cls)
        parts.append(g)

    return pd.concat(parts, ignore_index=True)

# =========================
# 4) FILTER ROWS READY FOR LSTM (168h history + 24h horizon)
# =========================
def filter_ready_rows(df: pd.DataFrame) -> pd.DataFrame:
    df = df.sort_values(["wardId", "tsHour"]).reset_index(drop=True).copy()
    df["t_index"] = df.groupby("wardId").cumcount()
    max_idx = df.groupby("wardId")["t_index"].transform("max")

    df = df[(df["t_index"] >= (HISTORY_HOURS - 1)) & (df["t_index"] <= (max_idx - HORIZON_HOURS - 1))]
    return df.drop(columns=["t_index"])

# =========================
# MAIN
# =========================
def main():
    if not MONGO_URL:
        raise RuntimeError("❌ MONGO_URL missing. Check ecofit-municipal-api/.env")

    client = MongoClient(MONGO_URL)
    db = client[DB_NAME]

    end = datetime.now(timezone.utc)
    start = end - timedelta(days=LOOKBACK_DAYS)

    print(f"📥 Pulling data from {start.isoformat()} to {end.isoformat()} ...")

    sparse = build_hourly_sparse(db, start, end)
    print("Sparse hourly rows:", len(sparse))

    if sparse.empty:
        print("❌ No data found in this range. Increase DATASET_LOOKBACK_DAYS or seed more data.")
        return

    full = make_continuous(sparse)
    print("Continuous hourly rows:", len(full))

    labeled = compute_next24_label(full)
    final_df = filter_ready_rows(labeled)

    # time features (helpful)
    final_df["hour"] = final_df["tsHour"].dt.hour
    final_df["dayOfWeek"] = final_df["tsHour"].dt.dayofweek  # 0=Mon

    final_df.to_csv(OUT_CSV, index=False)
    print(f"✅ Saved dataset: {OUT_CSV}")
    print("Final rows:", len(final_df))
    print("Class distribution:", final_df["riskClassNext24h"].value_counts().to_dict())

if __name__ == "__main__":
    main()