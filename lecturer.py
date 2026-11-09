from fastapi import APIRouter
from pydantic import BaseModel
from server import get_db_connection
from student import live_alerts 

lecturer_router = APIRouter(prefix="/lecturer")

class SessionStart(BaseModel):
    token: str
    lecturer_id: str
    course_name: str

@lecturer_router.post("/start_session")
async def start_session(data: SessionStart):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # שמירת המרצה והקורס האמיתיים לפי הקלט
    cursor.execute("INSERT OR IGNORE INTO users (id, first_name, last_name, role) VALUES (?, 'שם', 'מרצה', 'lecturer')", (data.lecturer_id,))
    cursor.execute("INSERT INTO courses (course_name, lecturer_id) VALUES (?, ?)", (data.course_name, data.lecturer_id))
    course_id = cursor.lastrowid
    
    # סטטוס התחלתי: רישום
    cursor.execute("INSERT INTO sessions (course_id, token, status) VALUES (?, ?, 'registration')", (course_id, data.token))
    
    conn.commit()
    conn.close()
    return {"status": "success", "message": "Session created"}

class SessionStatusUpdate(BaseModel):
    token: str
    status: str

# עדכון סטטוס השיעור לכל שלב שצריך
@lecturer_router.post("/update_status")
async def update_status(data: SessionStatusUpdate):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("UPDATE sessions SET status = ? WHERE token = ?", (data.status, data.token))
    conn.commit()
    conn.close()
    
    return {"status": "success"}

@lecturer_router.get("/live_updates/{token}")
async def get_live_updates(token: str):
    if token in live_alerts:
        updates = live_alerts[token]
        live_alerts[token] = {"volunteers": [], "questions": []}
        return updates
    return {"volunteers": [], "questions": []}