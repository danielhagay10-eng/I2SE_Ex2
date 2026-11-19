from fastapi import APIRouter, UploadFile, File
from pydantic import BaseModel
import pandas as pd
import base64
import cv2
import numpy as np
import io

lecturer_router = APIRouter(prefix="/lecturer")

class SessionStart(BaseModel):
    token: str
    lecturer_id: str
    course_name: str

class SessionStatusUpdate(BaseModel):
    token: str
    status: str

class ImageRequest(BaseModel):
    image: str
    token: str

@lecturer_router.post("/start_session")
async def start_session(data: SessionStart):
    from server import get_db_connection
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("INSERT OR IGNORE INTO users (id, first_name, last_name, role) VALUES (?, 'שם', 'מרצה', 'lecturer')", (data.lecturer_id,))
    cursor.execute("INSERT INTO courses (course_name, lecturer_id) VALUES (?, ?)", (data.course_name, data.lecturer_id))
    course_id = cursor.lastrowid
    
    cursor.execute("INSERT INTO sessions (course_id, token, status) VALUES (?, ?, 'registration')", (course_id, data.token))
    
    conn.commit()
    conn.close()
    return {"status": "success", "message": "Session created"}

@lecturer_router.post("/update_status")
async def update_status(data: SessionStatusUpdate):
    from server import get_db_connection
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE sessions SET status = ? WHERE token = ?", (data.status, data.token))
    conn.commit()
    conn.close()
    return {"status": "success"}

@lecturer_router.get("/live_updates/{token}")
async def live_updates(token: str):
    from student import live_alerts
    from server import get_db_connection
    
    questions = []
    volunteers = []
    understood_count = 0
    
    # שולף את כל ההתראות מהתור
    while not live_alerts.empty():
        alert = live_alerts.get()
        if alert["type"] == "question":
            questions.append(alert)
        elif alert["type"] == "volunteer":
            volunteers.append(alert["name"])
        elif alert["type"] == "understood":
            understood_count += 1
            
    # חישוב כמה תלמידים נוכחים בשיעור הזה כרגע (בשביל הסטטיסטיקה של המובן)
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) as cnt FROM attendance WHERE session_id = ?", (token,))
    total_attendance = cursor.fetchone()["cnt"]
    conn.close()
            
    return {
        "questions": questions, 
        "volunteers": volunteers, 
        "understood_count": understood_count,
        "total_attendance": total_attendance
    }

@lecturer_router.post("/upload_excel")
async def upload_excel(file: UploadFile = File(...)):
    contents = await file.read()
    
    df = pd.read_excel(io.BytesIO(contents))
    df['קבוצות'] = df['קבוצות'].fillna('').astype(str)
    students = df[df['קבוצות'].str.contains('3')]
    
    from server import get_db_connection
    conn = get_db_connection()
    cursor = conn.cursor()
    
    added_count = 0
    for _, row in students.iterrows():
        email = str(row['דוא"ל']).strip()
        first_name = str(row['שם פרטי']).strip()
        last_name = str(row['שם משפחה']).strip()
        
        cursor.execute('''
            INSERT OR IGNORE INTO users (id, first_name, last_name, role) 
            VALUES (?, ?, ?, 'student')
        ''', (email, first_name, last_name))
        added_count += 1
        
    conn.commit()
    conn.close()
    
    return {"status": "success", "message": f"סוננו ונוספו {added_count} סטודנטים בהצלחה למערכת!"}

@lecturer_router.get("/my_data/{lecturer_id}")
async def get_my_data(lecturer_id: str):
    from server import get_db_connection
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT COUNT(*) as total FROM users WHERE role = 'student'")
    total_students = cursor.fetchone()["total"]
    if total_students == 0:
        total_students = 1 
    
    cursor.execute("SELECT DISTINCT course_name FROM courses WHERE lecturer_id = ?", (lecturer_id,))
    courses = cursor.fetchall()
    courses_list = [{"name": c["course_name"], "students_count": total_students} for c in courses]
    
    cursor.execute('''
        SELECT s.id, c.course_name, s.status, s.token 
        FROM sessions s 
        JOIN courses c ON s.course_id = c.id 
        WHERE c.lecturer_id = ? 
        ORDER BY s.id DESC LIMIT 5
    ''', (lecturer_id,))
    sessions = cursor.fetchall()
    
    sessions_list = []
    for s in sessions:
        cursor.execute("SELECT COUNT(*) as attended FROM attendance WHERE session_token = ?", (s["token"],))
        attended_count = cursor.fetchone()["attended"]
        attendance_percent = int((attended_count / total_students) * 100)
        
        sessions_list.append({
            "id": s["id"], 
            "course_name": s["course_name"], 
            "status": s["status"],
            "attendance_percent": attendance_percent
        })
    
    conn.close()
    return {"courses": courses_list, "recent_sessions": sessions_list}

@lecturer_router.post("/count_faces")
async def count_faces(data: ImageRequest):
    from server import get_db_connection

    # 1. פענוח התמונה וספירת פרצופים
    encoded = data.image.split(",", 1)[1] if "," in data.image else data.image
    img_bytes = base64.b64decode(encoded)
    np_arr = np.frombuffer(img_bytes, np.uint8)
    img = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)

    if img is None:
        return {"face_count": 0, "scanned_count": 0, "error": "לא ניתן לפענח את התמונה"}

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    face_cascade = cv2.CascadeClassifier(
        cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
    )
    faces = face_cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(30, 30))
    face_count = len(faces)

    # 2. שליפת כמות סריקות ה-QR לשיעור הזה מה-DB
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT COUNT(*) as cnt FROM attendance WHERE session_token = ?", (data.token,))
        scanned_count = cursor.fetchone()["cnt"]
    except Exception:
        cursor.execute("SELECT COUNT(*) as cnt FROM attendance WHERE session_id = ?", (data.token,))
        scanned_count = cursor.fetchone()["cnt"]
    conn.close()

    return {"face_count": face_count, "scanned_count": scanned_count}