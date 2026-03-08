import os

# Dataset
DATASET_CSV = os.path.join("data", "ward_timeseries_hourly.csv")

# Model storage
MODEL_DIR = os.path.join("ml", "models")
LSTM_MODEL_PATH = os.path.join(MODEL_DIR, "lstm_model.pt")
SCALER_PATH = os.path.join(MODEL_DIR, "scaler.json")

# Columns
TIME_COL = "tsHour"
WARD_COL = "wardId"
LABEL_COL = "riskClassNext24h"

# Window
HISTORY_LEN = 168

# Classes
LABEL_TO_ID = {"LOW": 0, "MEDIUM": 1, "HIGH": 2, "EMERGENCY": 3}
ID_TO_LABEL = {v: k for k, v in LABEL_TO_ID.items()}

# Leakage columns (must never be used as inputs)
LEAKAGE_COLS = [
    "f_complaints_24h",
    "f_unresolved_24h",
    "f_missed_24h",
    "f_overflow_24h",
    "f_estKg_24h",
    "futureDemandScore",
]