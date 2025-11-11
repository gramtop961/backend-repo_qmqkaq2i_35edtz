"""
Database Schemas

Define your MongoDB collection schemas here using Pydantic models.
These schemas are used for data validation in your application.

Each Pydantic model represents a collection in your database.
Model name is converted to lowercase for the collection name:
- User -> "user" collection
- Product -> "product" collection
- BlogPost -> "blogs" collection
"""

from pydantic import BaseModel, Field
from typing import Optional
import datetime as dt

# ---------------- Mosque App Schemas ----------------

class SalahTime(BaseModel):
    """
    Daily salah and jamaat times for a specific date
    Collection: "salahtime"
    """
    date: dt.date = Field(..., description="Date for these timings (YYYY-MM-DD)")
    fajr: Optional[str] = Field(None, description="Adhan time for Fajr (HH:MM)")
    sunrise: Optional[str] = Field(None, description="Sunrise time (HH:MM)")
    dhuhr: Optional[str] = Field(None, description="Adhan time for Dhuhr (HH:MM)")
    asr: Optional[str] = Field(None, description="Adhan time for Asr (HH:MM)")
    maghrib: Optional[str] = Field(None, description="Adhan time for Maghrib (HH:MM)")
    isha: Optional[str] = Field(None, description="Adhan time for Isha (HH:MM)")

    fajr_jamaat: Optional[str] = Field(None, description="Jamaat time for Fajr (HH:MM)")
    dhuhr_jamaat: Optional[str] = Field(None, description="Jamaat time for Dhuhr (HH:MM)")
    asr_jamaat: Optional[str] = Field(None, description="Jamaat time for Asr (HH:MM)")
    maghrib_jamaat: Optional[str] = Field(None, description="Jamaat time for Maghrib (HH:MM)")
    isha_jamaat: Optional[str] = Field(None, description="Jamaat time for Isha (HH:MM)")

class Announcement(BaseModel):
    """Announcements to display on the screen"""
    message: str = Field(..., description="Announcement text")
    start_at: Optional[dt.datetime] = Field(None, description="Start showing at (UTC)")
    end_at: Optional[dt.datetime] = Field(None, description="Stop showing at (UTC)")
    priority: int = Field(1, ge=1, le=5, description="Priority 1 (low) to 5 (high)")
    active: bool = Field(True, description="Whether to show it")

class Asset(BaseModel):
    """Uploaded file metadata (images, pdfs, spreadsheets)"""
    filename: str
    content_type: str
    path: str

# --------------- Example legacy schemas (kept) ---------------

class User(BaseModel):
    name: str = Field(..., description="Full name")
    email: str = Field(..., description="Email address")
    address: str = Field(..., description="Address")
    age: Optional[int] = Field(None, ge=0, le=120, description="Age in years")
    is_active: bool = Field(True, description="Whether user is active")

class Product(BaseModel):
    title: str = Field(..., description="Product title")
    description: Optional[str] = Field(None, description="Product description")
    price: float = Field(..., ge=0, description="Price in dollars")
    category: str = Field(..., description="Product category")
    in_stock: bool = Field(True, description="Whether product is in stock")
