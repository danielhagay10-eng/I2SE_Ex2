from fastapi import APIRouter
from server import get_db_connection, AttendanceMark

# הגדרת הראוטר של התלמיד
student_router = APIRouter(prefix="/student", tags=["Student"])

@student_router.post("/mark_attendance")
def mark_attendance(data: AttendanceMark):
    conn = get_db_connection()
    conn.execute('INSERT INTO attendance (session_id, student_name) VALUES (?, ?)', 
                 (data.session_id, data.student_name))
    conn.commit()
    conn.close()
    return {"message": f"Attendance marked for {data.student_name}"}

@student_router.post("/ask_question")
def ask_question(question: str):
    # בהמשך נוסיף פה שמירה למסד הנתונים בשביל הכפתור האדום
    return {"message": "Question sent to lecturer"}