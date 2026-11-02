from fastapi import APIRouter
import uuid
from server import get_db_connection, SessionCreate

# הגדרת הראוטר של המרצה
lecturer_router = APIRouter(prefix="/lecturer", tags=["Lecturer"])

@lecturer_router.post("/open_session")
def open_session(data: SessionCreate):
    token = str(uuid.uuid4())[:8] # יצירת טוקן קצר ל-QR
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('INSERT INTO sessions (course_name, token, status) VALUES (?, ?, ?)', 
                   (data.course_name, token, 'active'))
    session_id = cursor.lastrowid
    conn.commit()
    conn.close()
    
    return {
        "message": "Session opened", 
        "session_id": session_id, 
        "qr_token": token
    }