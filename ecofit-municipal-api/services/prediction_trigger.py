# services/prediction_trigger.py
import os
import asyncio
from datetime import datetime, timezone
import httpx

BASE_URL = os.getenv("BASE_URL", "http://127.0.0.1:8000").rstrip("/")
ML_ENDPOINT = os.getenv("ML_TRIGGER_ENDPOINT", "/api/v1/ml/predict-and-store")
DEBOUNCE_SECONDS = float(os.getenv("PREDICTION_DEBOUNCE_SECONDS", "2.0"))


class PredictionTrigger:
    def __init__(self):
        self._lock = asyncio.Lock()
        self._task = None

    async def _call_ml(self) -> dict:
        url = f"{BASE_URL}{ML_ENDPOINT}"
        async with httpx.AsyncClient(timeout=120.0) as client:
            res = await client.post(url)
            res.raise_for_status()
            data = res.json()
        return {
            "ok": True,
            "triggeredAt": datetime.now(timezone.utc).isoformat(),
            "url": url,
            "ml_response": data,
        }

    async def _debounced_run(self):
        await asyncio.sleep(DEBOUNCE_SECONDS)
        async with self._lock:
            if asyncio.current_task() is not self._task:
                return
            self._task = None
        return await self._call_ml()

    async def trigger(self):
        async with self._lock:
            if self._task and not self._task.done():
                self._task.cancel()
            self._task = asyncio.create_task(self._debounced_run())
        return {"ok": True, "scheduled": True, "debounceSeconds": DEBOUNCE_SECONDS}


prediction_trigger = PredictionTrigger()