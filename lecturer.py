from fastapi import APIRouter, UploadFile, File
from pydantic import BaseModel
from datetime import datetime
import pandas as pd
import base64
import cv2
import numpy as np
import io
from ultralytics import YOLO

yolo_model = YOLO("yolov8s.pt")

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

    clean_lec = data.lecturer_id.strip().lower()
    clean_course = data.course_name.strip()

    cursor.execute(
        "INSERT OR IGNORE INTO users (id, first_name, last_name, role) VALUES (?, 'מרצה', '', 'lecturer')",
        (clean_lec,)
    )

    # שימוש בקורס קיים אם כבר נוצר בדשבורד, כדי לא לשכפל קורסים בכל שיעור
    cursor.execute(
        "SELECT id FROM courses WHERE course_name = ? AND LOWER(lecturer_id) = ? LIMIT 1",
        (clean_course, clean_lec)
    )
    existing = cursor.fetchone()
    if existing:
        course_id = existing["id"]
    else:
        created_at = datetime.now().strftime("%d/%m/%Y")
        cursor.execute(
            "INSERT INTO courses (course_name, lecturer_id, created_at) VALUES (?, ?, ?)",
            (clean_course, clean_lec, created_at)
        )
        course_id = cursor.lastrowid

    cursor.execute(
        "INSERT INTO sessions (course_id, token, status) VALUES (?, ?, 'registration')",
        (course_id, data.token)
    )

    conn.commit()
    conn.close()
    return {"status": "success", "message": "Session created", "course_id": course_id}


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

    while not live_alerts.empty():
        alert = live_alerts.get()
        if alert["type"] == "question":
            questions.append(alert)
        elif alert["type"] == "volunteer":
            volunteers.append(alert["name"])
        elif alert["type"] == "understood":
            understood_count += 1

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
        email = str(row['דוא"ל']).strip().lower()
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

    clean_lec = lecturer_id.strip().lower()
    cursor.execute("SELECT DISTINCT course_name FROM courses WHERE LOWER(lecturer_id) = ?", (clean_lec,))
    courses = cursor.fetchall()
    courses_list = []
    for c in courses:
        cursor.execute("SELECT COUNT(*) as cnt FROM course_students WHERE course_name = ?", (c["course_name"],))
        cnt = cursor.fetchone()["cnt"] or 0
        courses_list.append({"name": c["course_name"], "students_count": cnt})

    cursor.execute('''
        SELECT s.id, c.course_name, s.status, s.token
        FROM sessions s
        JOIN courses c ON s.course_id = c.id
        WHERE LOWER(c.lecturer_id) = ?
        ORDER BY s.id DESC LIMIT 5
    ''', (clean_lec,))
    sessions = cursor.fetchall()

    sessions_list = []
    for s in sessions:
        cursor.execute("SELECT COUNT(*) as attended FROM attendance WHERE session_id = ?", (s["token"],))
        attended_count = cursor.fetchone()["attended"]
        cursor.execute("SELECT COUNT(*) as cnt FROM course_students WHERE course_name = ?", (s["course_name"],))
        course_total = cursor.fetchone()["cnt"] or 1
        attendance_percent = min(int((attended_count / course_total) * 100), 100)

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

    encoded = data.image.split(",", 1)[1] if "," in data.image else data.image
    img_bytes = base64.b64decode(encoded)
    np_arr = np.frombuffer(img_bytes, np.uint8)
    img = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)

    if img is None:
        return {"face_count": 0, "scanned_count": 0, "error": "לא ניתן לפענח את התמונה"}

    results = yolo_model(img, classes=[0], conf=0.25, imgsz=1280, verbose=False)
    face_count = len(results[0].boxes)

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT COUNT(*) as cnt FROM attendance WHERE session_id = ?", (data.token,))
        scanned_count = cursor.fetchone()["cnt"]
    except Exception:
        cursor.execute("SELECT COUNT(*) as cnt FROM attendance WHERE session_token = ?", (data.token,))
        scanned_count = cursor.fetchone()["cnt"]
    conn.close()

    EPSILON = 1
    diff = scanned_count - face_count

    if diff > EPSILON:
        attendance_status = "too_many_scans"
    elif diff < -EPSILON:
        attendance_status = "fewer_scans"
    else:
        attendance_status = "ok"

    return {
        "face_count": face_count,
        "scanned_count": scanned_count,
        "diff": diff,
        "attendance_status": attendance_status
    }