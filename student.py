from fastapi import APIRouter
from server import get_db_connection, AttendanceMark

# הגדרת הראוטר של התלמיד
student_router = APIRouter(prefix="/student", tags=["Student"])
@student_router.post("/mark_attendance")
def mark_attendance(data: AttendanceMark):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # בדיקה האם תעודת הזהות כבר נרשמה לשיעור הזה
    existing = cursor.execute(
        'SELECT id FROM attendance WHERE session_id = ? AND student_id = ?', 
        (data.session_id, data.student_id)
    ).fetchone()
    
    if existing:
        conn.close()
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail="הסטודנט כבר רשם נוכחות לשיעור זה!")

    # שמירת כל הפרטים במסד הנתונים
    cursor.execute(
        'INSERT INTO attendance (session_id, student_id, first_name, last_name) VALUES (?, ?, ?, ?)', 
        (data.session_id, data.student_id, data.first_name, data.last_name)
    )
    conn.commit()
    conn.close()
    
    return {"message": f"Attendance marked for {data.first_name} {data.last_name}"}
@student_router.post("/volunteer")
async def volunteer(session_id: str, student_name: str):
    # בשלב הבא נשמור את זה במסד הנתונים כדי להציג למרצה
    print(f"Volunteer alert: {student_name} is ready to answer in session {session_id}")
    return {"status": "success", "message": "Volunteer registered"}

@student_router.post("/ask_question")
async def ask_question(session_id: str, student_name: str, question: str):
    # בשלב הבא נשמור את זה במסד הנתונים כדי להציג למרצה
    print(f"Question from {student_name} in session {session_id}: {question}")
    return {"status": "success", "message": "Question registered"}