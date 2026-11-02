import sqlite3
from pydantic import BaseModel

# חיבור למסד הנתונים SQLite
def get_db_connection():
    conn = sqlite3.connect('database.db')
    conn.row_factory = sqlite3.Row
    return conn

# יצירת הטבלאות (אם הן לא קיימות)
def init_db():
    conn = get_db_connection()
    conn.execute('''
        CREATE TABLE IF NOT EXISTS sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            course_name TEXT NOT NULL,
            token TEXT NOT NULL,
            status TEXT NOT NULL
        )
    ''')
    conn.execute('''
        CREATE TABLE IF NOT EXISTS attendance (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER,
            student_name TEXT NOT NULL
        )
    ''')
    conn.commit()
    conn.close()

# מודלים לקבלת נתונים מהמשתמש
class SessionCreate(BaseModel):
    course_name: str

class AttendanceMark(BaseModel):
    session_id: str
    student_name: str