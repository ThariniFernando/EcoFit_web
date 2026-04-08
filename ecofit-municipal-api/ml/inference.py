# backend/ml/inference.py
import json
import os
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd
import torch
from dotenv import load_dotenv

from ml.config_ml import LSTM_MODEL_PATH, SCALER_PATH, HISTORY_LEN, ID_TO_LABEL
from ml.model_lstm import LSTMClassifier
from ml.dataset import apply_scaler

load_dotenv()

WARD_FEATURES_COL = os.getenv("WARD_FEATURES_COL", "ward_hourly_features")
WARDS_MASTER_COL = os.getenv("WARDS_MASTER_COL", "wards_master")


class LSTMInference:
    def __init__(self, database=None, device: Optional[str] = None):
        self.database = database
        self.device = device if device is not None else ("cuda" if torch.cuda.is_available() else "cpu")
        self.model = None
        self.feature_cols = None
        self.scaler = None

    def load(self):
        with open(SCALER_PATH, "r", encoding="utf-8") as f:
            obj = json.load(f)

        self.feature_cols = obj["feature_cols"]
        self.scaler = obj["scaler"]

        ckpt = torch.load(LSTM_MODEL_PATH, map_location=self.device)
        self.model = LSTMClassifier(input_size=ckpt["input_size"])
        self.model.load_state_dict(ckpt["state_dict"])
        self.model.to(self.device)
        self.model.eval()

    @staticmethod
    def _clean_numpy_array(arr: np.ndarray) -> np.ndarray:
        return np.nan_to_num(arr, nan=0.0, posinf=0.0, neginf=0.0)

    @staticmethod
    def _normalize_probs(probs: np.ndarray) -> np.ndarray:
        probs = np.nan_to_num(probs, nan=0.0, posinf=0.0, neginf=0.0)
        total = float(probs.sum())

        if total <= 0.0:
            fallback = np.zeros(len(ID_TO_LABEL), dtype=np.float32)
            fallback[0] = 1.0
            return fallback

        return (probs / total).astype(np.float32)

    @torch.no_grad()
    def predict_from_docs(self, docs: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        docs = list of hourly feature documents for ONE ward.
        Must contain at least HISTORY_LEN rows and include tsHour + model feature columns.
        """
        if self.model is None:
            self.load()

        if len(docs) < HISTORY_LEN:
            raise ValueError(f"Need at least {HISTORY_LEN} docs, got {len(docs)}")

        df = pd.DataFrame(docs)

        if "tsHour" not in df.columns:
            raise ValueError("Mongo docs missing required field: tsHour")

        df["tsHour"] = pd.to_datetime(df["tsHour"], utc=True, errors="coerce")
        df = df.dropna(subset=["tsHour"]).sort_values("tsHour")
        df = df.tail(HISTORY_LEN)

        if len(df) < HISTORY_LEN:
            raise ValueError(f"After cleaning tsHour, only {len(df)} rows remain; need {HISTORY_LEN}")

        if "hour" in self.feature_cols and "hour" not in df.columns:
            df["hour"] = df["tsHour"].dt.hour

        if "dayOfWeek" in self.feature_cols and "dayOfWeek" not in df.columns:
            df["dayOfWeek"] = df["tsHour"].dt.dayofweek

        missing = [c for c in self.feature_cols if c not in df.columns]
        if missing:
            raise ValueError(f"Missing feature columns in docs: {missing}")

        for col in self.feature_cols:
            df[col] = pd.to_numeric(df[col], errors="coerce")

        df[self.feature_cols] = df[self.feature_cols].replace([np.inf, -np.inf], np.nan)
        df[self.feature_cols] = df[self.feature_cols].fillna(0.0)

        X = df[self.feature_cols].to_numpy(dtype=np.float32)
        X = X.reshape(1, HISTORY_LEN, -1)

        X = apply_scaler(X, self.scaler)
        X = self._clean_numpy_array(X)

        xb = torch.tensor(X, dtype=torch.float32).to(self.device)
        logits = self.model(xb)

        logits_np = logits.detach().cpu().numpy()
        logits_np = self._clean_numpy_array(logits_np)

        probs = torch.softmax(torch.tensor(logits_np, dtype=torch.float32), dim=1).cpu().numpy()[0]
        probs = self._normalize_probs(probs)

        pred_id = int(np.argmax(probs))

        return {
            "riskClass": ID_TO_LABEL[pred_id],
            "probabilities": probs.tolist(),
            "riskScore": float(probs[pred_id]),
        }

    async def _get_all_active_ward_ids(self) -> List[str]:
        if self.database is None:
            raise ValueError("database is required for predict_all_wards")

        ward_ids: List[str] = []
        async for w in self.database[WARDS_MASTER_COL].find(
            {"active": True},
            projection={"_id": 0, "wardId": 1},
        ):
            wid = str(w.get("wardId") or "").strip().upper()
            if wid:
                ward_ids.append(wid)
        return ward_ids

    async def _get_docs_for_ward(self, ward_id: str) -> List[Dict[str, Any]]:
        if self.database is None:
            raise ValueError("database is required for predict_all_wards")

        cursor = (
            self.database[WARD_FEATURES_COL]
            .find(
                {"wardId": ward_id},
                projection={"_id": 0},
            )
            .sort("tsHour", -1)
            .limit(HISTORY_LEN)
        )

        docs_desc: List[Dict[str, Any]] = []
        async for doc in cursor:
            docs_desc.append(doc)

        docs = list(reversed(docs_desc))
        return docs

    async def predict_all_wards(self) -> List[Dict[str, Any]]:
        if self.database is None:
            raise ValueError("database is required for predict_all_wards")

        if self.model is None:
            self.load()

        ward_ids = await self._get_all_active_ward_ids()
        print(f"✅ active wards found: {len(ward_ids)}")

        results: List[Dict[str, Any]] = []
        skipped: List[Dict[str, Any]] = []

        for ward_id in ward_ids:
            try:
                docs = await self._get_docs_for_ward(ward_id)

                if len(docs) < HISTORY_LEN:
                    skipped.append(
                        {
                            "wardId": ward_id,
                            "reason": f"not enough history: {len(docs)} < {HISTORY_LEN}",
                        }
                    )
                    continue

                pred = self.predict_from_docs(docs)
                pred["wardId"] = ward_id
                results.append(pred)

                print(
                    f"WARD={ward_id} "
                    f"riskClass={pred['riskClass']} "
                    f"riskScore={pred['riskScore']:.4f} "
                    f"probs={pred['probabilities']}"
                )

            except Exception as e:
                skipped.append({"wardId": ward_id, "reason": str(e)})

        print(f"✅ predictions created: {len(results)}")
        if skipped:
            print(f"⚠️ skipped wards: {len(skipped)}")
            for s in skipped[:10]:
                print("   ", s)

        return results