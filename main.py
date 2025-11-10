import os
from datetime import datetime, date
from typing import Optional, List

from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from database import db, create_document, get_documents
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
    if db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    today = date.today().isoformat()
    doc = db["salahtime"].find_one({"date": today}, {"_id": 0})
    return doc or {"date": today}


@app.get("/api/salah")
def get_salah_by_date(d: Optional[str] = None):
    if db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    if d is None:
        # return recent 30 entries
        cur = db["salahtime"].find({}, {"_id": 0}).sort("date", -1).limit(30)
        return list(cur)
    doc = db["salahtime"].find_one({"date": d}, {"_id": 0})
    return doc or {"date": d}


@app.post("/api/salah")
def upsert_salah(item: SalahTime):
    if db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    payload = item.model_dump()
    payload["updated_at"] = datetime.utcnow()
    db["salahtime"].update_one({"date": item.date.isoformat()}, {"$set": payload}, upsert=True)
    return {"status": "ok", "date": item.date.isoformat()}


# ---------------- Announcements Endpoints ----------------

@app.get("/api/announcements")
def get_active_announcements():
    if db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    now = datetime.utcnow()
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
        raise HTTPException(status_code=500, detail="Database not configured")
    _id = create_document("announcement", item)
    return {"status": "ok", "id": _id}


# ---------------- Assets Endpoints ----------------

@app.get("/api/assets")
def list_assets(limit: int = 20):
    if db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    cur = db["asset"].find({}, {"_id": 0}).sort("created_at", -1).limit(int(limit))
    return list(cur)


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
    meta = Asset(filename=safe_name, content_type=file.content_type or "application/octet-stream", path=url)
    create_document("asset", meta)
    return {"status": "ok", "url": url, "content_type": meta.content_type}


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
