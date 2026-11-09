from fastapi import APIRouter, HTTPException
from server import get_db_connection, AttendanceMark

# הגדרת הראוטר של התלמיד
student_router = APIRouter(prefix="/student", tags=["Student"])

# מאגר זמני להתראות חיות (עד שהמרצה יקרא אותן)
live_alerts = {}

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
    
    # שליפת שם הסטודנט כדי שהמרצה ידע מי זה
    cursor.execute("SELECT first_name, last_name FROM users WHERE id = ?", (student_id,))
    user = cursor.fetchone()
    student_name = f"{user['first_name']} {user['last_name']}" if user else "סטודנט לא ידוע"

    # שמירת נקודת השתתפות ב-DB
    cursor.execute('''
        INSERT INTO participation (session_id, student_id, action_type, points) 
        VALUES (?, ?, 'volunteer', 1)
    ''', (session_id, student_id))
    conn.commit()
    conn.close()

    # הוספה לתור ההתראות של השיעור הזה
    if session_id not in live_alerts:
        live_alerts[session_id] = {"volunteers": [], "questions": []}
    
    if student_name not in live_alerts[session_id]["volunteers"]:
        live_alerts[session_id]["volunteers"].append(student_name)

    return {"status": "success"}


@student_router.post("/ask_question")
async def ask_question(session_id: str, student_id: str, question: str):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT first_name, last_name FROM users WHERE id = ?", (student_id,))
    user = cursor.fetchone()
    student_name = f"{user['first_name']} {user['last_name']}" if user else "סטודנט לא ידוע"

    cursor.execute('''
        INSERT INTO participation (session_id, student_id, action_type, points) 
        VALUES (?, ?, 'question', 1)
    ''', (session_id, student_id))
    conn.commit()
    conn.close()

    # שמירת השאלה להתראה צפה
    if session_id not in live_alerts:
        live_alerts[session_id] = {"volunteers": [], "questions": []}
    
    live_alerts[session_id]["questions"].append({"name": student_name, "text": question})

    return {"status": "success"}


# כאן לבדוק האם השיעור התחיל 
@student_router.get("/check_status/{token}")
async def check_status(token: str):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT status FROM sessions WHERE token = ?", (token,))
    session = cursor.fetchone()
    conn.close()
    
    if session:
        return {"status": session["status"]}
    raise HTTPException(status_code=404, detail="Session not found")