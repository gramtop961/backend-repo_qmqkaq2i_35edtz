import os
from datetime import datetime, date
from typing import Optional, List, Dict, Any
import json
import mimetypes

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from database import db, create_document
from schemas import SalahTime, Announcement, Asset

app = FastAPI(title="Masjid Display Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Ensure uploads directory exists and is served statically
UPLOAD_DIR = os.path.join(os.getcwd(), "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")

# Fallback data directory for when DB is unavailable
DATA_DIR = os.path.join(os.getcwd(), "data")
os.makedirs(DATA_DIR, exist_ok=True)
SALAHS_FILE = os.path.join(DATA_DIR, "salah.json")
ANN_FILE = os.path.join(DATA_DIR, "announcements.json")


def _read_json(path: str) -> Any:
    try:
        if not os.path.exists(path):
            return None
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def _write_json(path: str, data: Any) -> None:
    tmp = f"{path}.tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)
    os.replace(tmp, path)


@app.get("/")
def read_root():
    return {"message": "Masjid Display Backend Running"}


@app.get("/api/hello")
def hello():
    return {"message": "Hello from the backend API!"}


@app.get("/test")
def test_database():
    """Test endpoint to check if database is available and accessible"""
    response = {
        "backend": "✅ Running",
        "database": "❌ Not Available",
        "database_url": None,
        "database_name": None,
        "connection_status": "Not Connected",
        "collections": []
    }

    try:
        if db is not None:
            response["database"] = "✅ Available"
            response["database_url"] = "✅ Configured"
            response["database_name"] = db.name if hasattr(db, 'name') else "✅ Connected"
            response["connection_status"] = "Connected"
            try:
                collections = db.list_collection_names()
                response["collections"] = collections[:10]
                response["database"] = "✅ Connected & Working"
            except Exception as e:
                response["database"] = f"⚠️  Connected but Error: {str(e)[:50]}"
        else:
            response["database"] = "⚠️  Available but not initialized"

    except Exception as e:
        response["database"] = f"❌ Error: {str(e)[:50]}"

    response["database_url"] = "✅ Set" if os.getenv("DATABASE_URL") else "❌ Not Set"
    response["database_name"] = "✅ Set" if os.getenv("DATABASE_NAME") else "❌ Not Set"

    return response


# ---------------- Salah Times Endpoints ----------------

@app.get("/api/salah/today")
def get_today_salah():
    today = date.today().isoformat()
    if db is None:
        # Fallback to local JSON store
        items = _read_json(SALAHS_FILE) or {}
        return items.get(today, {"date": today})
    doc = db["salahtime"].find_one({"date": today}, {"_id": 0})
    return doc or {"date": today}


@app.get("/api/salah")
def get_salah_by_date(d: Optional[str] = None):
    if db is None:
        # Fallback to local JSON store
        store = _read_json(SALAHS_FILE) or {}
        if d is None:
            # return recent up to 30 by date desc
            keys = sorted(store.keys(), reverse=True)[:30]
            return [store[k] for k in keys]
        return store.get(d, {"date": d})
    if d is None:
        # return recent 30 entries
        cur = db["salahtime"].find({}, {"_id": 0}).sort("date", -1).limit(30)
        return list(cur)
    doc = db["salahtime"].find_one({"date": d}, {"_id": 0})
    return doc or {"date": d}


@app.post("/api/salah")
def upsert_salah(item: SalahTime):
    payload = item.model_dump()
    # Ensure date is a JSON-serializable string
    payload["date"] = item.date.isoformat()
    payload["updated_at"] = datetime.utcnow().isoformat()

    if db is None:
        # Fallback: write to local JSON store keyed by date
        store = _read_json(SALAHS_FILE) or {}
        store[payload["date"]] = payload
        _write_json(SALAHS_FILE, store)
        return {"status": "ok", "date": payload["date"], "fallback": True}

    db["salahtime"].update_one(
        {"date": payload["date"]},
        {"$set": {**payload, "updated_at": datetime.utcnow().isoformat()}},
        upsert=True,
    )
    return {"status": "ok", "date": payload["date"]}


# ---------------- Announcements Endpoints ----------------

@app.get("/api/announcements")
def get_active_announcements():
    now = datetime.utcnow()
    if db is None:
        # Fallback: read from JSON and filter like DB would
        items: List[Dict[str, Any]] = _read_json(ANN_FILE) or []
        result = []
        for it in items:
            if not it.get("active", True):
                continue
            start_at = it.get("start_at")
            end_at = it.get("end_at")
            try:
                start_ok = (start_at is None) or (datetime.fromisoformat(start_at.replace("Z", "+00:00")) <= now)
                end_ok = (end_at is None) or (datetime.fromisoformat(end_at.replace("Z", "+00:00")) >= now)
            except Exception:
                start_ok = True
                end_ok = True
            if start_ok and end_ok:
                result.append(it)
        # sort by priority desc
        result.sort(key=lambda x: int(x.get("priority", 1)), reverse=True)
        return result

    filt = {
        "active": True,
        "$and": [
            {"$or": [{"start_at": None}, {"start_at": {"$lte": now}}]},
            {"$or": [{"end_at": None}, {"end_at": {"$gte": now}}]},
        ]
    }
    cur = db["announcement"].find(filt, {"_id": 0}).sort("priority", -1)
    return list(cur)


@app.post("/api/announcements")
def create_announcement(item: Announcement):
    if db is None:
        # Fallback: append to JSON list
        items: List[Dict[str, Any]] = _read_json(ANN_FILE) or []
        data = item.model_dump()
        data["created_at"] = datetime.utcnow().isoformat()
        items.append(data)
        _write_json(ANN_FILE, items)
        return {"status": "ok", "id": len(items), "fallback": True}
    _id = create_document("announcement", item)
    return {"status": "ok", "id": _id}


# ---------------- Assets Endpoints ----------------

@app.get("/api/assets")
def list_assets(limit: int = 20):
    # If DB available, prefer it
    if db is not None:
        cur = db["asset"].find({}, {"_id": 0}).sort("created_at", -1).limit(int(limit))
        return list(cur)

    # Fallback: list files from uploads directory
    items = []
    try:
        entries = sorted(
            (f for f in os.listdir(UPLOAD_DIR) if os.path.isfile(os.path.join(UPLOAD_DIR, f))),
            reverse=True,
        )
        for f in entries[: int(limit)]:
            path = os.path.join(UPLOAD_DIR, f)
            ctype, _ = mimetypes.guess_type(path)
            items.append({
                "filename": f,
                "content_type": ctype or "application/octet-stream",
                "path": f"/uploads/{f}",
            })
    except Exception:
        pass
    return items


# ---------------- File Upload Endpoints ----------------

@app.post("/api/upload")
async def upload_file(file: UploadFile = File(...)):
    if not file:
        raise HTTPException(status_code=400, detail="No file uploaded")
    filename = file.filename
    # ensure unique filename
    timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S%f")
    name, ext = os.path.splitext(filename)
    safe_name = f"{name}_{timestamp}{ext}"
    save_path = os.path.join(UPLOAD_DIR, safe_name)

    content = await file.read()
    with open(save_path, "wb") as f:
        f.write(content)

    url = f"/uploads/{safe_name}"

    # Try to record in DB; if DB not available, still succeed
    try:
        if db is not None:
            meta = Asset(filename=safe_name, content_type=file.content_type or "application/octet-stream", path=url)
            create_document("asset", meta)
    except Exception:
        # Ignore DB errors for upload success
        pass

    return {"status": "ok", "url": url, "content_type": file.content_type or "application/octet-stream"}


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
