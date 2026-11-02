import sqlite3
from pydantic import BaseModel, Field
from typing import Optional

def get_db_connection():
    conn = sqlite3.connect('database.db')
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    
    # טבלת משתמשים (מרצים וסטודנטים)
    conn.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id TEXT PRIMARY KEY,
            first_name TEXT NOT NULL,
            last_name TEXT NOT NULL,
            role TEXT NOT NULL, -- 'student' or 'lecturer'
            email TEXT
        )
    ''')
    
    # טבלת קורסים
    conn.execute('''
        CREATE TABLE IF NOT EXISTS courses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            course_name TEXT NOT NULL,
            lecturer_id TEXT NOT NULL,
            FOREIGN KEY (lecturer_id) REFERENCES users(id)
        )
    ''')
    
    # טבלת שיעורים (מעודכנת עם קישור לקורס)
    conn.execute('''
        CREATE TABLE IF NOT EXISTS sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            course_id INTEGER,
            token TEXT NOT NULL,
            status TEXT NOT NULL,
            FOREIGN KEY (course_id) REFERENCES courses(id)
        )
    ''')
    
    # טבלת נוכחות
    conn.execute('''
        CREATE TABLE IF NOT EXISTS attendance (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT,
            student_id TEXT NOT NULL,
            FOREIGN KEY (student_id) REFERENCES users(id)
        )
    ''')

    # טבלת סופר השתתפות (צבירת נקודות)
    conn.execute('''
        CREATE TABLE IF NOT EXISTS participation (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT,
            student_id TEXT NOT NULL,
            action_type TEXT NOT NULL, -- 'question', 'volunteer', 'view_recording'
            points INTEGER DEFAULT 1
        )
    ''')
    
    conn.commit()
    conn.close()

# מודלים לעבודה מול ה-API
class SessionCreate(BaseModel):
    course_id: int
class AttendanceMark(BaseModel):
    session_id: str
    student_id: str = Field(..., pattern=r"^\d{9}$")
    first_name: str
    last_name: str