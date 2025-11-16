"""
Database Schemas for Teen English Learning App

Each Pydantic model corresponds to a MongoDB collection. The collection name is the lowercase of the class name.

Use these schemas for validating data going into the database.
"""
from typing import List, Optional
from pydantic import BaseModel, Field
from datetime import datetime

class Student(BaseModel):
    name: str = Field(..., description="Student name (first name only recommended)")
    age: int = Field(..., ge=10, le=15, description="Age between 10 and 15")
    level: str = Field("A2", description="Approximate CEFR level: A1/A2/B1")
    guardian_email: Optional[str] = Field(None, description="Parent/guardian contact email")
    created_at: Optional[datetime] = None

class ChatMessage(BaseModel):
    student_id: Optional[str] = Field(None, description="Reference to Student _id")
    role: str = Field(..., description="'user' or 'tutor'")
    text: str = Field(..., description="Message content")
    corrections: Optional[List[str]] = Field(default=None, description="Corrections or tips associated with the message")
    created_at: Optional[datetime] = None

class ActivityResult(BaseModel):
    student_id: str = Field(..., description="Reference to Student _id")
    lesson_id: str = Field(..., description="Lesson identifier")
    activity_id: str = Field(..., description="Activity identifier inside the lesson")
    score: float = Field(..., ge=0, le=100, description="Score percentage 0-100")
    details: Optional[dict] = Field(default=None, description="Any extra details for report")
    created_at: Optional[datetime] = None

class PronunciationAttempt(BaseModel):
    student_id: Optional[str] = Field(None)
    target: str = Field(..., description="Target phrase or sentence")
    transcript: str = Field(..., description="Recognized speech transcript")
    similarity: Optional[float] = None
    created_at: Optional[datetime] = None

# These schemas are discoverable by the database viewer via the /schema endpoint in the backend.
