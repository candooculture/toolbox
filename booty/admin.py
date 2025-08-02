import json
import pandas as pd
from fastapi import APIRouter, HTTPException, Body
from pydantic import BaseModel
from typing import List
from fastapi.responses import FileResponse

admin_router = APIRouter(prefix="/admin")

# === File Paths ===
VISIBILITY_FILE = "visibility_settings.json"
BENCHMARK_FILE = "benchmarks/final_cleaned_benchmarks_with_certainty.csv"

# === Models ===


class VisibilitySetting(BaseModel):
    calculator: str
    visible: bool

# === Visibility Endpoints ===


@admin_router.get("/get-visibility")
async def get_visibility():
    try:
        with open(VISIBILITY_FILE, "r") as f:
            data = json.load(f)
        return {"status": "success", "data": data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@admin_router.post("/set-visibility")
async def set_visibility(payload: dict = Body(...)):
    try:
        updated = [VisibilitySetting(**item)
                   for item in payload["updated_visibility"]]
        with open(VISIBILITY_FILE, "w") as f:
            json.dump([v.dict() for v in updated], f, indent=2)
        return {"status": "success", "message": "Visibility settings updated."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# === Benchmark Endpoints ===


@admin_router.get("/get-benchmarks")
async def get_benchmarks():
    try:
        df = pd.read_csv(BENCHMARK_FILE)
        return {"status": "success", "data": df.to_dict(orient="records")}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@admin_router.post("/update-benchmarks")
async def update_benchmarks(updated_benchmarks: List[dict]):
    try:
        df = pd.DataFrame(updated_benchmarks)
        original_columns = pd.read_csv(
            BENCHMARK_FILE, nrows=1).columns.tolist()
        df = df[original_columns]
        df.to_csv(BENCHMARK_FILE, index=False)
        return {"status": "success", "message": "Benchmarks updated and saved successfully."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# === CSV Download Endpoint ===


@admin_router.get("/download-csv")
async def download_csv():
    try:
        return FileResponse(BENCHMARK_FILE, media_type="text/csv", filename="latest_benchmarks.csv")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
