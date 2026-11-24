import os
from fastapi import APIRouter, HTTPException
from server import get_db_connection, AttendanceMark
from queue import Queue

student_router = APIRouter(prefix="/student", tags=["Student"])
live_alerts = Queue()


@student_router.post("/mark_attendance")
async def mark_attendance(data: AttendanceMark):
    conn = get_db_connection()
    cursor = conn.cursor()

    # 1. בדיקה אם השיעור קיים ושליפת הקורס והמרצה שלו
    cursor.execute('''
        SELECT s.id, s.course_id, c.course_name, c.lecturer_id
        FROM sessions s
        LEFT JOIN courses c ON s.course_id = c.id
        WHERE s.token = ?
    ''', (data.session_id,))
    session = cursor.fetchone()
    if not session:
        conn.close()
        raise HTTPException(status_code=404, detail="קוד שיעור לא תקין")

    clean_student = data.student_id.strip().lower()
    course_name = session["course_name"]
    course_lecturer = (session["lecturer_id"] or "").strip().lower()

    demo_student_email = os.getenv("DEMO_STUDENT_EMAIL", "demo.student@smartlms.local").strip().lower()
    demo_lecturer_email = os.getenv("DEMO_LECTURER_EMAIL", "demo.lecturer@smartlms.local").strip().lower()

    # 2. אכיפת הרשאות קורס וגישת דמו מבוקרת
    if course_name:
        if clean_student == demo_student_email:
            if course_lecturer != demo_lecturer_email:
                conn.close()
                raise HTTPException(
                    status_code=403,
                    detail="תלמיד דמו מורשה להיכנס אך ורק לשיעורי הדגמה של מרצה דמו."
                )
        else:
            cursor.execute(
                "SELECT 1 FROM course_students WHERE course_name = ? AND LOWER(student_email) = ?",
                (course_name, clean_student)
            )
            if not cursor.fetchone():
                conn.close()
                raise HTTPException(
                    status_code=403,
                    detail=f"אינך רשום לקורס '{course_name}' ולכן אינך מורשה להירשם לשיעור זה."
                )

    # 3. הוספת הסטודנט לטבלת המשתמשים אם טרם נרשם
    cursor.execute('''
        INSERT OR IGNORE INTO users (id, first_name, last_name, role)
        VALUES (?, ?, ?, 'student')
    ''', (clean_student, data.first_name, data.last_name))

    # 4. מניעת כפילויות ברישום נוכחות
    cursor.execute(
        "SELECT id FROM attendance WHERE session_id = ? AND LOWER(student_id) = ?",
        (data.session_id, clean_student)
    )
    if cursor.fetchone():
        conn.close()
        raise HTTPException(status_code=400, detail="כבר נרשמת לשיעור זה")

    # 5. רישום נוכחות בטבלת הנוכחות
    cursor.execute(
        "INSERT INTO attendance (session_id, student_id) VALUES (?, ?)",
        (data.session_id, clean_student)
    )

    conn.commit()
    conn.close()

    return {"status": "success", "message": "Attendance marked successfully"}


@student_router.post("/volunteer")
async def volunteer(session_id: str, student_id: str):
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT first_name, last_name FROM users WHERE LOWER(id) = ?", (student_id.strip().lower(),))
    user = cursor.fetchone()
    student_name = f"{user['first_name']} {user['last_name']}" if user else "סטודנט לא ידוע"

    cursor.execute('''
        INSERT INTO participation (session_id, student_id, action_type, points)
        VALUES (?, ?, 'volunteer', 1)
    ''', (session_id, student_id.strip().lower()))
    conn.commit()
    conn.close()

    live_alerts.put({"type": "volunteer", "name": student_name})
    return {"status": "success"}


@student_router.post("/ask_question")
async def ask_question(session_id: str, student_id: str, question: str):
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT first_name, last_name FROM users WHERE LOWER(id) = ?", (student_id.strip().lower(),))
    user = cursor.fetchone()
    student_name = f"{user['first_name']} {user['last_name']}" if user else "סטודנט לא ידוע"

    cursor.execute('''
        INSERT INTO participation (session_id, student_id, action_type, points)
        VALUES (?, ?, 'question', 1)
    ''', (session_id, student_id.strip().lower()))
    conn.commit()
    conn.close()

    live_alerts.put({"type": "question", "name": student_name, "text": question})
    return {"status": "success"}


@student_router.post("/understood")
async def understood(session_id: str, student_id: str):
    live_alerts.put({"type": "understood"})
    return {"status": "success"}


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