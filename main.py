import os
from typing import List, Optional
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from bson import ObjectId

from database import db, create_document, get_documents
from schemas import Student, ChatMessage, ActivityResult, PronunciationAttempt

app = FastAPI(title="Teen English Learning API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def read_root():
    return {"message": "Teen English Learning API is running"}

@app.get("/test")
def test_database():
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
            response["database_url"] = "✅ Set" if os.getenv("DATABASE_URL") else "❌ Not Set"
            response["database_name"] = db.name if hasattr(db, 'name') else "Unknown"
            response["connection_status"] = "Connected"
            try:
                collections = db.list_collection_names()
                response["collections"] = collections[:10]
                response["database"] = "✅ Connected & Working"
            except Exception as e:
                response["database"] = f"⚠️ Connected but error: {str(e)[:80]}"
        else:
            response["database"] = "⚠️ Available but not initialized"
    except Exception as e:
        response["database"] = f"❌ Error: {str(e)[:80]}"

    response["database_url"] = "✅ Set" if os.getenv("DATABASE_URL") else "❌ Not Set"
    response["database_name"] = "✅ Set" if os.getenv("DATABASE_NAME") else "❌ Not Set"
    return response

# -------- Schema exposure for viewer/tools --------
class SchemaInfo(BaseModel):
    name: str
    fields: dict

@app.get("/schema")
def get_schema():
    return {
        "student": Student.model_json_schema(),
        "chatmessage": ChatMessage.model_json_schema(),
        "activityresult": ActivityResult.model_json_schema(),
        "pronunciationattempt": PronunciationAttempt.model_json_schema(),
    }

# -------- Core API Endpoints --------

@app.post("/students", response_model=dict)
def create_student(student: Student):
    try:
        _id = create_document("student", student)
        return {"id": _id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/students", response_model=List[dict])
def list_students(limit: Optional[int] = 50):
    try:
        docs = get_documents("student", limit=limit)
        for d in docs:
            d["id"] = str(d.get("_id"))
            d.pop("_id", None)
        return docs
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

class TutorRequest(BaseModel):
    student_id: Optional[str] = None
    message: str

class TutorResponse(BaseModel):
    reply: str
    tips: List[str] = []
    grammar_notes: List[str] = []

@app.post("/tutor/chat", response_model=TutorResponse)
def tutor_chat(payload: TutorRequest):
    """
    Basic rule-based NLP to simulate guidance. In production, plug an LLM here.
    Also stores chat history for analytics.
    """
    user_text = payload.message.strip()
    reply = ""
    tips: List[str] = []
    grammar: List[str] = []

    # simple heuristic feedback
    if any(word in user_text.lower() for word in ["i is", "she go", "he go", "they was"]):
        grammar.append("Subject-verb agreement: use 'I am', 'she goes', 'they were'.")
    if user_text and user_text[0].islower():
        grammar.append("Start sentences with a capital letter.")
    if not user_text.endswith(('.', '!', '?')):
        grammar.append("End sentences with a period or question mark.")

    # conversational reply template
    if "favorite" in user_text.lower():
        reply = "Cool! Tell me more about your favorites. Why do you like them?"
    elif "school" in user_text.lower():
        reply = "School can be fun and challenging. What's your best subject and why?"
    else:
        reply = "Thanks for sharing! Can you add 1-2 more details in another sentence?"

    # Save user message
    try:
        create_document("chatmessage", ChatMessage(student_id=payload.student_id, role="user", text=user_text, corrections=grammar))
        create_document("chatmessage", ChatMessage(student_id=payload.student_id, role="tutor", text=reply, corrections=tips))
    except Exception:
        # ignore storage error to keep chat responsive
        pass

    return TutorResponse(reply=reply, tips=tips, grammar_notes=grammar)

class PronunciationRequest(BaseModel):
    student_id: Optional[str] = None
    target: str
    transcript: str

class PronunciationFeedback(BaseModel):
    similarity: float
    advice: List[str]

@app.post("/tutor/pronunciation", response_model=PronunciationFeedback)
def pronunciation_feedback(payload: PronunciationRequest):
    # naive similarity based on token overlap Jaccard
    target_tokens = set(payload.target.lower().split())
    said_tokens = set(payload.transcript.lower().split())
    if not target_tokens:
        sim = 0.0
    else:
        sim = len(target_tokens & said_tokens) / len(target_tokens | said_tokens)

    advice: List[str] = []
    if sim < 0.6:
        advice.append("Slow down and speak each word clearly.")
        advice.append("Pay attention to ending sounds like -s, -ed.")
    else:
        advice.append("Great job! Try adding natural intonation.")

    try:
        create_document("pronunciationattempt", PronunciationAttempt(student_id=payload.student_id, target=payload.target, transcript=payload.transcript, similarity=sim))
    except Exception:
        pass

    return PronunciationFeedback(similarity=round(sim, 2), advice=advice)

class ActivitySubmission(BaseModel):
    student_id: str
    lesson_id: str
    activity_id: str
    answers: dict

class ActivityFeedback(BaseModel):
    score: float
    feedback: List[str]

@app.post("/lessons/activity/submit", response_model=ActivityFeedback)
def submit_activity(payload: ActivitySubmission):
    # simple auto-grader: if answers contain at least one non-empty, give partial credit
    non_empty = sum(1 for v in payload.answers.values() if str(v).strip())
    total = max(len(payload.answers), 1)
    score = (non_empty / total) * 100
    feedback: List[str] = []
    if score < 60:
        feedback.append("Let's review key vocabulary and try again.")
    elif score < 85:
        feedback.append("Nice work! A few small mistakes to fix.")
    else:
        feedback.append("Excellent! You're mastering this topic.")

    try:
        create_document("activityresult", ActivityResult(student_id=payload.student_id, lesson_id=payload.lesson_id, activity_id=payload.activity_id, score=score, details={"answers": payload.answers}))
    except Exception:
        pass

    return ActivityFeedback(score=round(score, 1), feedback=feedback)

# Basic progress aggregation endpoint
@app.get("/progress/{student_id}")
def get_progress(student_id: str):
    try:
        # Aggregate simple stats
        vocab_growth = db["activityresult"].count_documents({"student_id": student_id})
        chats = db["chatmessage"].count_documents({"student_id": student_id})
        pronunciation = db["pronunciationattempt"].count_documents({"student_id": student_id})
        avg_pron = 0.0
        try:
            cursor = db["pronunciationattempt"].find({"student_id": student_id})
            sims = [doc.get("similarity", 0) for doc in cursor]
            if sims:
                avg_pron = sum(sims) / len(sims)
        except Exception:
            pass
        return {
            "student_id": student_id,
            "vocabulary_growth": vocab_growth,  # proxy via activity submissions
            "messages_exchanged": chats,
            "avg_pronunciation_similarity": round(avg_pron, 2)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
