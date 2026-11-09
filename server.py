from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import sqlite3

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def get_db_connection():
    conn = sqlite3.connect("attendance.db")
    conn.row_factory = sqlite3.Row
    return conn

# --- פונקציה חדשה: בניית מסד הנתונים אם הוא חסר ---
def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''CREATE TABLE IF NOT EXISTS users (id TEXT PRIMARY KEY, first_name TEXT, last_name TEXT, role TEXT)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS courses (id INTEGER PRIMARY KEY AUTOINCREMENT, course_name TEXT, lecturer_id TEXT)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS sessions (id INTEGER PRIMARY KEY AUTOINCREMENT, course_id INTEGER, token TEXT, status TEXT)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS attendance (id INTEGER PRIMARY KEY AUTOINCREMENT, session_id TEXT, student_id TEXT)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS participation (id INTEGER PRIMARY KEY AUTOINCREMENT, session_id TEXT, student_id TEXT, action_type TEXT, points INTEGER)''')
    
    conn.commit()
    conn.close()

# הפעלת יצירת הטבלאות מיד כשהשרת עולה
init_db()
# ----------------------------------------------------

class AttendanceMark(BaseModel):
    session_id: str
    student_id: str
    first_name: str
    last_name: str

class LoginRequest(BaseModel):
    id: str

@app.post("/login")
async def login(data: LoginRequest):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT role, first_name, last_name FROM users WHERE id = ?", (data.id,))
    user = cursor.fetchone()
    conn.close()

    if user:
        return {"status": "success", "role": user["role"], "name": f"{user['first_name']} {user['last_name']}"}
    else:
        raise HTTPException(status_code=401, detail="תעודת זהות לא נמצאה במערכת")

from lecturer import lecturer_router
from student import student_router

app.include_router(lecturer_router)
app.include_router(student_router)