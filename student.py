from fastapi import APIRouter
from server import get_db_connection, AttendanceMark
from fastapi import APIRouter, HTTPException
from server import get_db_connection

# הגדרת הראוטר של התלמיד
student_router = APIRouter(prefix="/student", tags=["Student"])
@student_router.post("/mark_attendance")
async def mark_attendance(data: AttendanceMark):
    conn = get_db_connection()
    cursor = conn.cursor()

    # 1. בדיקה אם השיעור קיים
    cursor.execute("SELECT id FROM sessions WHERE token = ?", (data.session_id,))
    session = cursor.fetchone()
    if not session:
        conn.close()
        raise HTTPException(status_code=404, detail="קוד שיעור לא תקין")

    # 2. הוספת הסטודנט לטבלת המשתמשים (אם הוא לא שם כבר)
    cursor.execute('''
        INSERT OR IGNORE INTO users (id, first_name, last_name, role)
        VALUES (?, ?, ?, 'student')
    ''', (data.student_id, data.first_name, data.last_name))

    # 3. מניעת כפילויות ברישום נוכחות
    cursor.execute("SELECT id FROM attendance WHERE session_id = ? AND student_id = ?", (data.session_id, data.student_id))
    if cursor.fetchone():
        conn.close()
        raise HTTPException(status_code=400, detail="כבר נרשמת לשיעור זה")

    # 4. רישום נוכחות בטבלת הנוכחות המעודכנת
    cursor.execute("INSERT INTO attendance (session_id, student_id) VALUES (?, ?)", (data.session_id, data.student_id))
    
    conn.commit()
    conn.close()

    return {"status": "success", "message": "Attendance marked successfully"}
@student_router.post("/volunteer")
async def volunteer(session_id: str, student_id: str):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO participation (session_id, student_id, action_type, points) 
        VALUES (?, ?, 'volunteer', 1)
    ''', (session_id, student_id))
    conn.commit()
    conn.close()
    return {"status": "success", "message": "Volunteer registered"}

@student_router.post("/ask_question")
async def ask_question(session_id: str, student_id: str, question: str):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO participation (session_id, student_id, action_type, points) 
        VALUES (?, ?, 'question', 1)
    ''', (session_id, student_id))
    
    # כאן אפשר לשמור גם את תוכן השאלה עצמה לטבלה נפרדת בעתיד
    print(f"Question from {student_id}: {question}")
    
    conn.commit()
    conn.close()
    return {"status": "success", "message": "Question registered"}