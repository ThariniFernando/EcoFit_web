import os
import asyncio
from datetime import datetime, timezone

DEBOUNCE_SECONDS = float(os.getenv("PREDICTION_DEBOUNCE_SECONDS", "2.0"))


class PredictionTrigger:
    def __init__(self):
        self._lock = asyncio.Lock()
        self._task = None

    async def _call_ml(self) -> dict:
        # FIX: direct in-process call instead of HTTP round-trip to self
        from routers.ml_router import run_predict_and_store
        result = await run_predict_and_store()
        return {
            "ok": True,
            "triggeredAt": datetime.now(timezone.utc).isoformat(),
            "result": result,
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