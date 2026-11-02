from fastapi import APIRouter
from server import get_db_connection, AttendanceMark

# הגדרת הראוטר של התלמיד
student_router = APIRouter(prefix="/student", tags=["Student"])

@student_router.post("/mark_attendance")
def mark_attendance(data: AttendanceMark):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # 1. בדיקה האם הסטודנט כבר נרשם לשיעור הזה
    existing = cursor.execute(
        'SELECT id FROM attendance WHERE session_id = ? AND student_name = ?', 
        (data.session_id, data.student_name)
    ).fetchone()
    
    if existing:
        conn.close()
        # מחזירים שגיאה ללקוח אם הוא כבר רשום
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail="הסטודנט כבר רשם נוכחות לשיעור זה!")

    # 2. אם הוא לא רשום - שומרים כרגיל
    cursor.execute(
        'INSERT INTO attendance (session_id, student_name) VALUES (?, ?)', 
        (data.session_id, data.student_name)
    )
    conn.commit()
    conn.close()
    
    return {"message": f"Attendance marked for {data.student_name}"}