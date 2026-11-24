import sqlite3
from pydantic import BaseModel


def get_db_connection():
    conn = sqlite3.connect("attendance.db")
    conn.row_factory = sqlite3.Row
    return conn


class AttendanceMark(BaseModel):
    session_id: str
    student_id: str
    first_name: str
    last_name: str


class LoginRequest(BaseModel):
    id: str


def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute('''CREATE TABLE IF NOT EXISTS users (
        id TEXT PRIMARY KEY,
        first_name TEXT,
        last_name TEXT,
        role TEXT
    )''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS approved_lecturers (
        email TEXT PRIMARY KEY,
        full_name TEXT,
        added_at TEXT
    )''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS courses (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        course_name TEXT,
        lecturer_id TEXT,
        created_at TEXT
    )''')
    try:
        cursor.execute("ALTER TABLE courses ADD COLUMN created_at TEXT DEFAULT ''")
    except Exception:
        pass

    cursor.execute('''CREATE TABLE IF NOT EXISTS sessions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        course_id INTEGER,
        token TEXT,
        status TEXT
    )''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS attendance (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        session_id TEXT,
        student_id TEXT
    )''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS participation (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        session_id TEXT,
        student_id TEXT,
        action_type TEXT,
        points INTEGER
    )''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS course_students (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        course_name TEXT NOT NULL,
        student_email TEXT NOT NULL,
        full_name TEXT NOT NULL,
        id_number TEXT DEFAULT '',
        UNIQUE(course_name, student_email)
    )''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS course_staff (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        course_name TEXT NOT NULL,
        staff_email TEXT NOT NULL,
        full_name TEXT NOT NULL,
        role_title TEXT DEFAULT 'מתרגל',
        UNIQUE(course_name, staff_email)
    )''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS lessons (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        course_name TEXT,
        title TEXT,
        date_str TEXT,
        materials_json TEXT,
        ai_summary TEXT
    )''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS surveys (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        course_name TEXT,
        questions_json TEXT,
        status TEXT,
        end_timestamp REAL,
        created_at TEXT
    )''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS survey_votes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        survey_id INTEGER,
        student_id TEXT,
        answers_json TEXT,
        UNIQUE(survey_id, student_id)
    )''')

    conn.commit()
    conn.close()