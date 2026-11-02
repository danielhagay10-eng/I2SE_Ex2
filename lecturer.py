from fastapi import APIRouter
from pydantic import BaseModel
from server import get_db_connection

lecturer_router = APIRouter(prefix="/lecturer")

class SessionStart(BaseModel):
    token: str

@lecturer_router.post("/start_session")
async def start_session(data: SessionStart):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # מכיוון שה-DB ריק, ניצור מרצה וקורס פיקטיביים רק כדי שהשיעור יוכל להיווצר
    cursor.execute("INSERT OR IGNORE INTO users (id, first_name, last_name, role) VALUES ('111', 'מרצה', 'דמו', 'lecturer')")
    cursor.execute("INSERT OR IGNORE INTO courses (id, course_name, lecturer_id) VALUES (1, 'קורס דמו', '111')")
    
    # שמירת קוד ה-QR של השיעור
    cursor.execute("INSERT INTO sessions (course_id, token, status) VALUES (1, ?, 'active')", (data.token,))
    
    conn.commit()
    conn.close()
    return {"status": "success", "message": "Session created in DB"}