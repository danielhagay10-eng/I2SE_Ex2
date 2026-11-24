from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
import json
import time
import os
import uuid
import shutil
import smtplib
from email.message import EmailMessage
from datetime import datetime
from server import get_db_connection
from google import genai

dashboard_router = APIRouter(prefix="/api", tags=["Dashboard"])


class CourseCreate(BaseModel):
    course_name: str
    lecturer_id: str


class CourseRename(BaseModel):
    course_name: str
    lecturer_id: str


class StaffAddRequest(BaseModel):
    course_name: str
    staff_email: str
    full_name: Optional[str] = ""
    role_title: str = "מתרגל"


class SurveyLaunch(BaseModel):
    course_name: str
    questions: List[Dict[str, Any]]
    duration_seconds: int


class SurveyVote(BaseModel):
    survey_id: int
    student_id: str
    answers: Dict[str, str]


class StudentQuestionEmail(BaseModel):
    course_name: str
    student_email: str
    student_name: str
    recipient_email: Optional[str] = None
    subject: str
    body: str


class LecturerBroadcastEmail(BaseModel):
    course_name: str
    subject: str
    body: str


def _table_columns(cursor, table_name: str) -> set:
    try:
        cursor.execute(f"PRAGMA table_info({table_name})")
        return {row["name"] for row in cursor.fetchall()}
    except Exception:
        return set()


def _ensure_tables(cursor):
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
    try:
        cursor.execute("ALTER TABLE courses ADD COLUMN created_at TEXT DEFAULT ''")
    except Exception:
        pass


def _get_course_staff_list(cursor, course_name: str) -> List[Dict[str, str]]:
    _ensure_tables(cursor)
    staff = []
    seen = set()

    # 1. מרצה הקורס הראשי מתוך טבלת courses
    cursor.execute(
        """SELECT c.lecturer_id, u.first_name, u.last_name
           FROM courses c
           LEFT JOIN users u ON LOWER(c.lecturer_id) = LOWER(u.id)
           WHERE c.course_name = ? AND c.lecturer_id LIKE '%@%'
           LIMIT 1""",
        (course_name,)
    )
    lec = cursor.fetchone()
    if lec and lec["lecturer_id"]:
        lec_email = lec["lecturer_id"].strip().lower()
        lec_name = f"{lec['first_name'] or ''} {lec['last_name'] or ''}".strip() or lec_email.split("@")[0]
        staff.append({
            "id": 0,
            "email": lec_email,
            "name": lec_name,
            "role_title": "מרצה הקורס"
        })
        seen.add(lec_email)

    # 2. מתרגלים ומרצים נוספים מתוך course_staff
    cursor.execute(
        "SELECT id, staff_email, full_name, role_title FROM course_staff WHERE course_name = ? ORDER BY id ASC",
        (course_name,)
    )
    for row in cursor.fetchall():
        em = row["staff_email"].strip().lower()
        if em not in seen:
            seen.add(em)
            staff.append({
                "id": row["id"],
                "email": em,
                "name": row["full_name"] or em.split("@")[0],
                "role_title": row["role_title"] or "מתרגל"
            })

    # 3. גיבוי אם הקורס נוצר ללא lecturer_id תקין
    if not staff:
        cursor.execute("SELECT id, first_name, last_name FROM users WHERE role = 'lecturer' AND id LIKE '%@%' LIMIT 1")
        fallback = cursor.fetchone()
        if fallback:
            em = fallback["id"].strip().lower()
            nm = f"{fallback['first_name'] or ''} {fallback['last_name'] or ''}".strip() or em.split("@")[0]
            staff.append({
                "id": 0,
                "email": em,
                "name": nm,
                "role_title": "מרצה הקורס"
            })

    return staff


def _get_course_lecturer_email(cursor, course_name: str) -> str:
    staff = _get_course_staff_list(cursor, course_name)
    if staff:
        return staff[0]["email"]
    raise HTTPException(
        status_code=400,
        detail="לא נמצא חשבון Google של מרצה המשויך לקורס זה."
    )


def _send_smtp_email(recipients: List[str], subject: str, body: str, reply_to: str = None, use_bcc: bool = False):
    smtp_email = os.getenv("SMTP_EMAIL", "").strip()
    smtp_password = os.getenv("SMTP_PASSWORD", "").strip()

    if not smtp_email or not smtp_password:
        raise HTTPException(
            status_code=500,
            detail="חסרים פרטי שליחת מייל (SMTP_EMAIL / SMTP_PASSWORD) בקובץ .env"
        )

    if not recipients:
        raise HTTPException(status_code=400, detail="לא נמצאו כתובות מייל ליעד השליחה")

    smtp_host = os.getenv("SMTP_HOST", "smtp.gmail.com").strip()

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = smtp_email

    if use_bcc and len(recipients) > 1:
        msg["To"] = smtp_email
        msg["Bcc"] = ", ".join(recipients)
    else:
        msg["To"] = ", ".join(recipients)

    if reply_to and "@" in reply_to:
        msg["Reply-To"] = reply_to

    msg.set_content(body)

    try:
        try:
            with smtplib.SMTP(smtp_host, 587, timeout=15) as server:
                server.ehlo()
                server.starttls()
                server.ehlo()
                server.login(smtp_email, smtp_password)
                server.send_message(msg)
                return
        except (smtplib.SMTPAuthenticationError, smtplib.SMTPRecipientsRefused):
            raise
        except Exception:
            with smtplib.SMTP_SSL(smtp_host, 465, timeout=15) as server:
                server.login(smtp_email, smtp_password)
                server.send_message(msg)

    except smtplib.SMTPAuthenticationError:
        raise HTTPException(
            status_code=500,
            detail="שגיאת התחברות ל-Gmail: ודא שהזנת סיסמת אפליקציה (App Password) בת 16 תווים ללא רווחים ב-SMTP_PASSWORD"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"שגיאה בשליחת המייל: {str(e)}")


def _parse_roster_excel(file_obj) -> tuple[List[Dict[str, str]], List[Dict[str, str]]]:
    try:
        import openpyxl
    except ImportError:
        raise HTTPException(
            status_code=500,
            detail="חסרה הספרייה openpyxl לקריאת קבצי Excel. הרץ בטרמינל: pip install openpyxl"
        )

    wb = openpyxl.load_workbook(file_obj, data_only=True)
    ws = wb.active
    rows = list(ws.iter_rows(values_only=True))
    if not rows:
        return [], []

    headers = [str(cell).strip().lower() if cell is not None else "" for cell in rows[0]]

    def find_col(candidates):
        for idx, h in enumerate(headers):
            for c in candidates:
                if c == h or c in h:
                    return idx
        return None

    email_idx = find_col(['כתובת דוא"ל', 'כתובת דוא״ל', 'דוא"ל', 'אימייל', 'מייל', 'email', 'e-mail'])
    first_idx = find_col(['שם פרטי', 'first name', 'firstname'])
    last_idx = find_col(['שם משפחה', 'last name', 'lastname', 'surname'])
    full_idx = find_col(['שם מלא', 'full name', 'fullname', 'name', 'שם'])
    id_idx = find_col(['מספר זיהוי', 'תעודת זהות', 'ת"ז', 'מזהה', 'id number', 'id'])
    role_idx = find_col(['תפקידים', 'תפקיד', 'roles', 'role'])

    if email_idx is None:
        raise HTTPException(
            status_code=400,
            detail="לא נמצאה עמודת כתובת דוא\"ל בקובץ האקסל. ודא שיש עמודה עם כותרת 'כתובת דוא\"ל' או 'Email'."
        )

    students = []
    staff = []
    seen = set()

    for r in rows[1:]:
        if not r or all(v is None or str(v).strip() == "" for v in r):
            continue

        raw_email = str(r[email_idx]).strip().lower() if (email_idx < len(r) and r[email_idx] is not None) else ""
        if "@" not in raw_email or raw_email in seen:
            continue
        seen.add(raw_email)

        raw_id = str(r[id_idx]).strip() if (id_idx is not None and id_idx < len(r) and r[id_idx] is not None) else ""
        if raw_id.endswith(".0"):
            raw_id = raw_id[:-2]

        first_name = str(r[first_idx]).strip() if (first_idx is not None and first_idx < len(r) and r[first_idx] is not None) else ""
        last_name = str(r[last_idx]).strip() if (last_idx is not None and last_idx < len(r) and r[last_idx] is not None) else ""

        if first_name or last_name:
            full_name = f"{first_name} {last_name}".strip()
        elif full_idx is not None and full_idx < len(r) and r[full_idx] is not None:
            full_name = str(r[full_idx]).strip()
        else:
            full_name = raw_email.split("@")[0]

        role_val = ""
        if role_idx is not None and role_idx < len(r) and r[role_idx] is not None:
            role_val = str(r[role_idx]).strip().lower()

        if any(k in role_val for k in ("מתרגל", "teaching assistant", "ta")):
            staff.append({
                "staff_email": raw_email,
                "full_name": full_name,
                "role_title": "מתרגל"
            })
            continue

        if any(k in role_val for k in ("מרצה", "teacher", "lecturer", "manager", "admin")):
            staff.append({
                "staff_email": raw_email,
                "full_name": full_name,
                "role_title": "מרצה"
            })
            continue

        students.append({
            "student_email": raw_email,
            "full_name": full_name,
            "first_name": first_name or full_name.split(" ")[0],
            "last_name": last_name or (" ".join(full_name.split(" ")[1:]) if " " in full_name else ""),
            "id_number": raw_id
        })

    return students, staff


# --- 0. ניהול קורסים של מרצה וקורסים של תלמיד ---
@dashboard_router.get("/lecturer/courses")
async def get_lecturer_courses(lecturer_id: str):
    clean_lec = lecturer_id.strip().lower()
    conn = get_db_connection()
    cursor = conn.cursor()
    _ensure_tables(cursor)
    conn.commit()

    cursor.execute(
        "SELECT id, course_name, lecturer_id, created_at FROM courses WHERE LOWER(lecturer_id) = ? ORDER BY id ASC",
        (clean_lec,)
    )
    rows = cursor.fetchall()

    courses = []
    for r in rows:
        cursor.execute("SELECT COUNT(*) as cnt FROM course_students WHERE course_name = ?", (r["course_name"],))
        students_count = cursor.fetchone()["cnt"] or 0
        courses.append({
            "id": r["id"],
            "course_name": r["course_name"],
            "lecturer_id": r["lecturer_id"],
            "created_at": r["created_at"] or "",
            "students_count": students_count
        })

    conn.close()
    return {"courses": courses}


@dashboard_router.post("/lecturer/courses")
async def create_lecturer_course(data: CourseCreate):
    clean_name = data.course_name.strip()
    clean_lec = data.lecturer_id.strip().lower()
    if not clean_name:
        raise HTTPException(status_code=400, detail="נא להזין שם קורס")
    if not clean_lec:
        raise HTTPException(status_code=400, detail="חסר מזהה מרצה")

    conn = get_db_connection()
    cursor = conn.cursor()
    _ensure_tables(cursor)

    cursor.execute(
        "SELECT id FROM courses WHERE course_name = ? AND LOWER(lecturer_id) = ?",
        (clean_name, clean_lec)
    )
    if cursor.fetchone():
        conn.close()
        raise HTTPException(status_code=400, detail="כבר קיים אצלך קורס בשם זה")

    created_at = datetime.now().strftime("%d/%m/%Y")
    cursor.execute(
        "INSERT INTO courses (course_name, lecturer_id, created_at) VALUES (?, ?, ?)",
        (clean_name, clean_lec, created_at)
    )
    course_id = cursor.lastrowid
    conn.commit()
    conn.close()

    return {
        "status": "success",
        "course": {
            "id": course_id,
            "course_name": clean_name,
            "lecturer_id": clean_lec,
            "created_at": created_at,
            "students_count": 0
        }
    }


@dashboard_router.put("/lecturer/courses/{course_id}")
async def rename_lecturer_course(course_id: int, data: CourseRename):
    new_name = data.course_name.strip()
    clean_lec = data.lecturer_id.strip().lower()
    if not new_name:
        raise HTTPException(status_code=400, detail="נא להזין שם קורס חדש")

    conn = get_db_connection()
    cursor = conn.cursor()
    _ensure_tables(cursor)

    cursor.execute("SELECT id, course_name, lecturer_id, created_at FROM courses WHERE id = ?", (course_id,))
    course = cursor.fetchone()
    if not course:
        conn.close()
        raise HTTPException(status_code=404, detail="הקורס לא נמצא")

    if (course["lecturer_id"] or "").strip().lower() != clean_lec:
        conn.close()
        raise HTTPException(status_code=403, detail="אין הרשאה לערוך קורס של מרצה אחר")

    old_name = course["course_name"]
    if old_name != new_name:
        cursor.execute(
            "SELECT id FROM courses WHERE course_name = ? AND LOWER(lecturer_id) = ? AND id != ?",
            (new_name, clean_lec, course_id)
        )
        if cursor.fetchone():
            conn.close()
            raise HTTPException(status_code=400, detail="כבר קיים אצלך קורס אחר בשם זה")

        # עדכון שם הקורס בלבד — created_at נשמר ללא שינוי!
        cursor.execute("UPDATE courses SET course_name = ? WHERE id = ?", (new_name, course_id))
        cursor.execute("UPDATE course_students SET course_name = ? WHERE course_name = ?", (new_name, old_name))
        cursor.execute("UPDATE course_staff SET course_name = ? WHERE course_name = ?", (new_name, old_name))
        cursor.execute("UPDATE lessons SET course_name = ? WHERE course_name = ?", (new_name, old_name))
        cursor.execute("UPDATE surveys SET course_name = ? WHERE course_name = ?", (new_name, old_name))
        conn.commit()

    created_at = course["created_at"] or ""
    conn.close()
    return {
        "status": "success",
        "id": course_id,
        "course_name": new_name,
        "created_at": created_at
    }


@dashboard_router.delete("/lecturer/courses/{course_id}")
async def delete_lecturer_course(course_id: int, lecturer_id: str):
    clean_lec = lecturer_id.strip().lower()
    conn = get_db_connection()
    cursor = conn.cursor()
    _ensure_tables(cursor)

    cursor.execute("SELECT id, course_name, lecturer_id FROM courses WHERE id = ?", (course_id,))
    course = cursor.fetchone()
    if not course:
        conn.close()
        raise HTTPException(status_code=404, detail="הקורס לא נמצא")

    if (course["lecturer_id"] or "").strip().lower() != clean_lec:
        conn.close()
        raise HTTPException(status_code=403, detail="אין הרשאה למחוק קורס של מרצה אחר")

    cname = course["course_name"]
    cursor.execute("DELETE FROM courses WHERE id = ?", (course_id,))
    cursor.execute("DELETE FROM course_students WHERE course_name = ?", (cname,))
    cursor.execute("DELETE FROM course_staff WHERE course_name = ?", (cname,))
    cursor.execute("DELETE FROM lessons WHERE course_name = ?", (cname,))
    cursor.execute("DELETE FROM surveys WHERE course_name = ?", (cname,))
    cursor.execute("DELETE FROM sessions WHERE course_id = ?", (course_id,))

    conn.commit()
    conn.close()
    return {"status": "deleted"}


@dashboard_router.get("/student/courses")
async def get_student_courses(student_email: str):
    clean_email = student_email.strip().lower()
    demo_student_email = os.getenv("DEMO_STUDENT_EMAIL", "demo.student@smartlms.local").strip().lower()
    demo_lecturer_email = os.getenv("DEMO_LECTURER_EMAIL", "demo.lecturer@smartlms.local").strip().lower()

    conn = get_db_connection()
    cursor = conn.cursor()
    _ensure_tables(cursor)
    conn.commit()

    if clean_email == demo_student_email:
        # סביבת דמו מבוקרת: רואה רק את הקורסים של מרצה הדמו
        cursor.execute(
            """SELECT c.id, c.course_name, c.lecturer_id, c.created_at, u.first_name, u.last_name
               FROM courses c
               LEFT JOIN users u ON LOWER(c.lecturer_id) = LOWER(u.id)
               WHERE LOWER(c.lecturer_id) = ?
               ORDER BY c.id ASC""",
            (demo_lecturer_email,)
        )
    else:
        # תלמיד רגיל: רואה אך ורק קורסים שבהם המרצה הכניס אותו לרשימת האקסל של הקורס
        cursor.execute(
            """SELECT DISTINCT c.id, c.course_name, c.lecturer_id, c.created_at, u.first_name, u.last_name
               FROM course_students cs
               JOIN courses c ON cs.course_name = c.course_name
               LEFT JOIN users u ON LOWER(c.lecturer_id) = LOWER(u.id)
               WHERE LOWER(cs.student_email) = ?
                 AND LOWER(COALESCE(c.lecturer_id, '')) != ?
               ORDER BY c.id ASC""",
            (clean_email, demo_lecturer_email)
        )

    rows = cursor.fetchall()
    courses = []
    for r in rows:
        lec_name = f"{r['first_name'] or ''} {r['last_name'] or ''}".strip() or (r["lecturer_id"] or "מרצה")
        courses.append({
            "id": r["id"],
            "course_name": r["course_name"],
            "lecturer_email": r["lecturer_id"] or "",
            "lecturer_name": lec_name,
            "created_at": r["created_at"] or ""
        })

    conn.close()
    return {"courses": courses}


# --- 1. ניהול רשימת סטודנטים וצוות קורס (מרצה + מתרגלים), נוכחות ונקודות ---
@dashboard_router.post("/course/students/upload-excel")
async def upload_course_students_excel(
    course_name: str = Form(...),
    file: UploadFile = File(...)
):
    if not file.filename.lower().endswith((".xlsx", ".xlsm")):
        raise HTTPException(status_code=400, detail="נא להעלות קובץ Excel תקין בפורמט .xlsx")

    students, staff_members = _parse_roster_excel(file.file)
    if not students:
        raise HTTPException(status_code=400, detail="לא נמצאו סטודנטים עם כתובת מייל תקינה בקובץ האקסל")

    conn = get_db_connection()
    cursor = conn.cursor()
    _ensure_tables(cursor)

    cursor.execute("DELETE FROM course_students WHERE course_name = ?", (course_name,))

    user_cols = _table_columns(cursor, "users")
    for st in students:
        cursor.execute(
            "INSERT INTO course_students (course_name, student_email, full_name, id_number) VALUES (?, ?, ?, ?)",
            (course_name, st["student_email"], st["full_name"], st["id_number"])
        )
        if {"id", "first_name", "last_name", "role"}.issubset(user_cols):
            cursor.execute(
                "INSERT OR IGNORE INTO users (id, first_name, last_name, role) VALUES (?, ?, ?, 'student')",
                (st["student_email"], st["first_name"], st["last_name"])
            )

    for member in staff_members:
        cursor.execute(
            """INSERT INTO course_staff (course_name, staff_email, full_name, role_title)
               VALUES (?, ?, ?, ?)
               ON CONFLICT(course_name, staff_email) DO UPDATE SET
               full_name = excluded.full_name, role_title = excluded.role_title""",
            (course_name, member["staff_email"], member["full_name"], member["role_title"])
        )

    conn.commit()
    conn.close()
    return {
        "status": "success",
        "imported_count": len(students),
        "staff_imported_count": len(staff_members),
        "course_name": course_name
    }


@dashboard_router.get("/course/staff")
async def get_course_staff(course_name: str):
    conn = get_db_connection()
    cursor = conn.cursor()
    staff = _get_course_staff_list(cursor, course_name)
    conn.commit()
    conn.close()
    return {"staff": staff}


@dashboard_router.post("/course/staff")
async def add_course_staff(data: StaffAddRequest):
    email = data.staff_email.strip().lower()
    if "@" not in email:
        raise HTTPException(status_code=400, detail="נא להזין כתובת אימייל תקינה")

    full_name = (data.full_name or "").strip() or email.split("@")[0]
    role_title = (data.role_title or "מתרגל").strip()

    conn = get_db_connection()
    cursor = conn.cursor()
    _ensure_tables(cursor)
    cursor.execute(
        """INSERT INTO course_staff (course_name, staff_email, full_name, role_title)
           VALUES (?, ?, ?, ?)
           ON CONFLICT(course_name, staff_email) DO UPDATE SET
           full_name = excluded.full_name, role_title = excluded.role_title""",
        (data.course_name.strip(), email, full_name, role_title)
    )
    conn.commit()
    conn.close()
    return {"status": "success"}


@dashboard_router.delete("/course/staff/{staff_id}")
async def remove_course_staff(staff_id: int):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM course_staff WHERE id = ?", (staff_id,))
    conn.commit()
    conn.close()
    return {"status": "deleted"}


@dashboard_router.get("/course/students")
async def get_course_students(course_name: str):
    conn = get_db_connection()
    cursor = conn.cursor()
    _ensure_tables(cursor)
    conn.commit()

    session_cols = _table_columns(cursor, "sessions")
    course_cols = _table_columns(cursor, "courses")
    att_cols = _table_columns(cursor, "attendance")
    part_cols = _table_columns(cursor, "participation")

    if "course_id" in session_cols and {"id", "course_name"}.issubset(course_cols):
        cursor.execute(
            """SELECT COUNT(*) as total
               FROM sessions s
               JOIN courses c ON s.course_id = c.id
               WHERE c.course_name = ?""",
            (course_name,)
        )
        total_sessions = cursor.fetchone()["total"] or 0
    elif "course_name" in session_cols:
        cursor.execute("SELECT COUNT(*) as total FROM sessions WHERE course_name = ?", (course_name,))
        total_sessions = cursor.fetchone()["total"] or 0
    else:
        cursor.execute("SELECT COUNT(*) as total FROM sessions")
        total_sessions = cursor.fetchone()["total"] or 0

    cursor.execute(
        "SELECT student_email, full_name, id_number FROM course_students WHERE course_name = ? ORDER BY full_name ASC",
        (course_name,)
    )
    roster = cursor.fetchall()

    result = []
    for row in roster:
        email = row["student_email"].strip().lower()
        full_name = row["full_name"]
        id_num = (row["id_number"] or "").strip()

        identifiers = [email]
        if id_num and id_num != email:
            identifiers.append(id_num)
        placeholders = ",".join("?" for _ in identifiers)

        attended = 0
        if total_sessions > 0 and att_cols:
            if "course_id" in session_cols and {"id", "course_name"}.issubset(course_cols):
                cursor.execute(
                    f"""SELECT COUNT(DISTINCT a.session_id) as cnt
                        FROM attendance a
                        JOIN sessions s ON (CAST(a.session_id AS TEXT) = CAST(s.id AS TEXT) OR a.session_id = s.token)
                        JOIN courses c ON s.course_id = c.id
                        WHERE c.course_name = ? AND LOWER(a.student_id) IN ({placeholders})""",
                    [course_name] + identifiers
                )
                attended = cursor.fetchone()["cnt"] or 0
            elif "course_name" in session_cols:
                cursor.execute(
                    f"""SELECT COUNT(DISTINCT a.session_id) as cnt
                        FROM attendance a
                        JOIN sessions s ON (CAST(a.session_id AS TEXT) = CAST(s.id AS TEXT) OR a.session_id = s.token)
                        WHERE s.course_name = ? AND LOWER(a.student_id) IN ({placeholders})""",
                    [course_name] + identifiers
                )
                attended = cursor.fetchone()["cnt"] or 0

        points = 0
        if part_cols:
            if "course_id" in session_cols and {"id", "course_name"}.issubset(course_cols) and "session_id" in part_cols:
                cursor.execute(
                    f"""SELECT COALESCE(SUM(p.points), 0) as pts
                        FROM participation p
                        JOIN sessions s ON (CAST(p.session_id AS TEXT) = CAST(s.id AS TEXT) OR p.session_id = s.token)
                        JOIN courses c ON s.course_id = c.id
                        WHERE c.course_name = ? AND LOWER(p.student_id) IN ({placeholders})""",
                    [course_name] + identifiers
                )
                points = cursor.fetchone()["pts"] or 0
            elif "course_name" in part_cols:
                cursor.execute(
                    f"SELECT COALESCE(SUM(points), 0) as pts FROM participation WHERE course_name = ? AND LOWER(student_id) IN ({placeholders})",
                    [course_name] + identifiers
                )
                points = cursor.fetchone()["pts"] or 0

        pct = round((attended / total_sessions) * 100) if total_sessions > 0 else 0
        result.append({
            "student_id": email,
            "name": full_name,
            "attended": min(attended, total_sessions),
            "total_sessions": total_sessions,
            "percentage": min(pct, 100),
            "points": points
        })

    conn.close()
    return {"students": result, "total_sessions": total_sessions}


# --- 2. ניהול שיעורים והעלאת קבצים אמיתיים ---
@dashboard_router.get("/lessons")
async def get_lessons(course_name: str):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM lessons WHERE course_name = ? ORDER BY id DESC", (course_name,))
    rows = cursor.fetchall()
    conn.close()

    lessons = []
    for r in rows:
        raw_materials = json.loads(r["materials_json"] or "[]")
        normalized = []
        for item in raw_materials:
            if isinstance(item, str):
                normalized.append({"name": item, "url": None, "ext": os.path.splitext(item)[1].lower()})
            else:
                normalized.append(item)

        lessons.append({
            "id": r["id"],
            "course_name": r["course_name"],
            "title": r["title"],
            "date_str": r["date_str"],
            "materials": normalized
        })
    return {"lessons": lessons}


@dashboard_router.post("/lessons/with-files")
async def create_lesson_with_files(
    course_name: str = Form(...),
    title: str = Form(...),
    date_str: str = Form(...),
    files: List[UploadFile] = File(default=[])
):
    os.makedirs("uploads", exist_ok=True)
    saved_materials = []

    for f in files:
        if not f.filename:
            continue
        safe_ext = os.path.splitext(f.filename)[1].lower()
        unique_name = f"{uuid.uuid4().hex[:8]}_{f.filename}"
        file_path = os.path.join("uploads", unique_name)
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(f.file, buffer)

        saved_materials.append({
            "name": f.filename,
            "url": f"/uploads/{unique_name}",
            "ext": safe_ext
        })

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO lessons (course_name, title, date_str, materials_json) VALUES (?, ?, ?, ?)",
        (course_name, title, date_str, json.dumps(saved_materials, ensure_ascii=False))
    )
    lesson_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return {"status": "success", "id": lesson_id, "materials": saved_materials}


@dashboard_router.delete("/lessons/{lesson_id}")
async def delete_lesson(lesson_id: int):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM lessons WHERE id = ?", (lesson_id,))
    conn.commit()
    conn.close()
    return {"status": "deleted"}


# --- 3. מערכת סקרים בזמן אמת ---
@dashboard_router.post("/surveys/launch")
async def launch_survey(data: SurveyLaunch):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE surveys SET status = 'closed' WHERE status = 'active' AND course_name = ?", (data.course_name,))

    end_ts = time.time() + data.duration_seconds
    created_str = datetime.now().strftime("%d/%m/%Y %H:%M")

    cursor.execute(
        "INSERT INTO surveys (course_name, questions_json, status, end_timestamp, created_at) VALUES (?, ?, 'active', ?, ?)",
        (data.course_name, json.dumps(data.questions, ensure_ascii=False), end_ts, created_str)
    )
    survey_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return {"status": "success", "survey_id": survey_id, "end_timestamp": end_ts}


@dashboard_router.get("/surveys/active")
async def get_active_survey(course_name: Optional[str] = None):
    conn = get_db_connection()
    cursor = conn.cursor()
    if course_name:
        cursor.execute(
            "SELECT * FROM surveys WHERE status = 'active' AND course_name = ? ORDER BY id DESC LIMIT 1",
            (course_name,)
        )
    else:
        cursor.execute("SELECT * FROM surveys WHERE status = 'active' ORDER BY id DESC LIMIT 1")
    survey = cursor.fetchone()

    if not survey:
        conn.close()
        return {"active": False}

    seconds_left = int(survey["end_timestamp"] - time.time())
    if seconds_left <= 0:
        cursor.execute("UPDATE surveys SET status = 'closed' WHERE id = ?", (survey["id"],))
        conn.commit()
        conn.close()
        return {"active": False}

    cursor.execute("SELECT answers_json FROM survey_votes WHERE survey_id = ?", (survey["id"],))
    votes_rows = cursor.fetchall()
    conn.close()

    questions = json.loads(survey["questions_json"])
    vote_counts = {}
    for row in votes_rows:
        ans = json.loads(row["answers_json"])
        for q_idx, chosen_opt in ans.items():
            vote_counts.setdefault(q_idx, {})
            vote_counts[q_idx][chosen_opt] = vote_counts[q_idx].get(chosen_opt, 0) + 1

    return {
        "active": True,
        "survey_id": survey["id"],
        "questions": questions,
        "seconds_left": seconds_left,
        "total_votes": len(votes_rows),
        "vote_counts": vote_counts
    }


@dashboard_router.post("/surveys/extend/{survey_id}")
async def extend_survey(survey_id: int, extra_seconds: int = 120):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE surveys SET end_timestamp = end_timestamp + ? WHERE id = ?", (extra_seconds, survey_id))
    conn.commit()
    conn.close()
    return {"status": "extended"}


@dashboard_router.post("/surveys/close/{survey_id}")
async def close_survey(survey_id: int):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE surveys SET status = 'closed' WHERE id = ?", (survey_id,))
    conn.commit()
    conn.close()
    return {"status": "closed"}


@dashboard_router.post("/surveys/vote")
async def vote_survey(data: SurveyVote):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO survey_votes (survey_id, student_id, answers_json) VALUES (?, ?, ?)",
            (data.survey_id, data.student_id, json.dumps(data.answers, ensure_ascii=False))
        )
        conn.commit()
    except Exception:
        conn.close()
        raise HTTPException(status_code=400, detail="כבר הצבעת בסקר זה")
    conn.close()
    return {"status": "voted"}


@dashboard_router.get("/surveys/history")
async def get_surveys_history(course_name: Optional[str] = None):
    conn = get_db_connection()
    cursor = conn.cursor()
    if course_name:
        cursor.execute(
            "SELECT * FROM surveys WHERE status = 'closed' AND course_name = ? ORDER BY id DESC",
            (course_name,)
        )
    else:
        cursor.execute("SELECT * FROM surveys WHERE status = 'closed' ORDER BY id DESC")
    surveys = cursor.fetchall()

    history = []
    for s in surveys:
        cursor.execute("SELECT answers_json FROM survey_votes WHERE survey_id = ?", (s["id"],))
        votes_rows = cursor.fetchall()
        questions = json.loads(s["questions_json"])
        vote_counts = {}
        for row in votes_rows:
            ans = json.loads(row["answers_json"])
            for q_idx, chosen_opt in ans.items():
                vote_counts.setdefault(q_idx, {})
                vote_counts[q_idx][chosen_opt] = vote_counts[q_idx].get(chosen_opt, 0) + 1

        history.append({
            "id": s["id"],
            "created_at": s["created_at"],
            "questions": questions,
            "total_votes": len(votes_rows),
            "vote_counts": vote_counts
        })

    conn.close()
    return {"history": history}


# --- 4. סיכום שיעור וקבצים/סרטונים באמצעות Gemini ---
@dashboard_router.post("/lessons/{lesson_id}/summarize")
async def summarize_lesson(lesson_id: int):
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("ALTER TABLE lessons ADD COLUMN ai_summary TEXT")
        conn.commit()
    except Exception:
        pass

    cursor.execute("SELECT * FROM lessons WHERE id = ?", (lesson_id,))
    lesson = cursor.fetchone()

    if not lesson:
        conn.close()
        raise HTTPException(status_code=404, detail="השיעור לא נמצא")

    lesson_dict = dict(lesson)
    if lesson_dict.get("ai_summary"):
        conn.close()
        return {"summary": lesson_dict["ai_summary"], "cached": True}

    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        conn.close()
        raise HTTPException(status_code=500, detail="חסר מפתח GEMINI_API_KEY בקובץ .env")

    client = genai.Client(api_key=api_key)
    materials = json.loads(lesson_dict.get("materials_json") or "[]")
    contents = []
    uploaded_refs = []

    try:
        for m in materials:
            if isinstance(m, dict) and m.get("url"):
                local_path = m["url"].lstrip("/")
                if os.path.exists(local_path):
                    file_ref = client.files.upload(file=local_path)
                    while getattr(file_ref.state, "name", "") == "PROCESSING":
                        time.sleep(2)
                        file_ref = client.files.get(name=file_ref.name)
                    contents.append(file_ref)
                    uploaded_refs.append(file_ref)

        prompt = (
            f"אתה עוזר הוראה אקדמי. סכם בעברית בצורה ברורה, מסודרת ותמציתית את השיעור "
            f"'{lesson_dict['title']}' בקורס '{lesson_dict['course_name']}'. "
            f"התבסס על הקבצים/הסרטונים המצורפים (אם צורפו), וכלול:\n"
            f"1. סיכום עיקרי השיעור בנקודות.\n"
            f"2. מושגים מרכזיים ודגשים חשובים למבחן.\n"
            f"3. 3 שאלות חזרה קצרות לתרגול עצמי."
        )
        contents.append(prompt)

        candidate_models = ["models/gemini-3.8-flash"]
        excluded_keywords = ("embedding", "imagen", "veo", "aqa", "tts", "robotics", "computer-use", "deep-research")
        try:
            for m in client.models.list():
                name = getattr(m, "name", "")
                lower = name.lower()
                if "gemini" in lower and not any(bad in lower for bad in excluded_keywords):
                    if name not in candidate_models:
                        candidate_models.append(name)
        except Exception:
            pass

        response = None
        last_error = None

        for model_name in candidate_models:
            try:
                response = client.models.generate_content(
                    model=model_name,
                    contents=contents
                )
                if response and getattr(response, "text", None):
                    break
            except Exception as api_err:
                last_error = api_err
                continue

        if not response or not getattr(response, "text", None):
            raise RuntimeError(f"כל המודלים עמוסים כרגע ({last_error})")

        summary_text = response.text

        cursor.execute("UPDATE lessons SET ai_summary = ? WHERE id = ?", (summary_text, lesson_id))
        conn.commit()

        return {"summary": summary_text, "cached": False}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"שגיאה ביצירת סיכום AI: {str(e)}")
    finally:
        conn.close()
        for ref in uploaded_refs:
            try:
                client.files.delete(name=ref.name)
            except Exception:
                pass


# --- 5. שליחת מיילים ישירה בין חשבונות Google (סטודנט <-> מרצה / מתרגל) ---
@dashboard_router.post("/emails/ask-lecturer")
async def send_question_to_lecturer(data: StudentQuestionEmail):
    if not data.subject.strip() or not data.body.strip():
        raise HTTPException(status_code=400, detail="נא למלא נושא ותוכן לשאלה")

    conn = get_db_connection()
    cursor = conn.cursor()
    staff_list = _get_course_staff_list(cursor, data.course_name)
    conn.close()

    if not staff_list:
        raise HTTPException(status_code=400, detail="לא נמצא מרצה או מתרגל המשויך לקורס זה.")

    allowed_map = {s["email"]: s for s in staff_list}
    if data.recipient_email and data.recipient_email.strip():
        chosen_email = data.recipient_email.strip().lower()
        if chosen_email not in allowed_map:
            raise HTTPException(status_code=400, detail="הנמען שנבחר אינו שייך לסגל הקורס")
        chosen_staff = allowed_map[chosen_email]
    else:
        chosen_staff = staff_list[0]

    real_recipient_email = chosen_staff["email"]
    test_email = os.getenv("TEST_EMAIL", "").strip()

    if test_email:
        target_recipients = [test_email]
        email_subject = f"[בדיקה -> {real_recipient_email}] {data.subject}"
        email_body = (
            f"מצב בדיקה (TEST_EMAIL): מייל זה היה נשלח במקור אל {chosen_staff['name']} ({chosen_staff['role_title']}): {real_recipient_email}\n"
            f"--------------------------------------------------\n"
            f"קורס: {data.course_name}\n"
            f"מאת הסטודנט/ית: {data.student_name} ({data.student_email})\n\n"
            f"{data.body}\n"
        )
    else:
        target_recipients = [real_recipient_email]
        email_subject = f"[{data.course_name}] {data.subject}"
        email_body = (
            f"שלום {chosen_staff['name']},\n"
            f"התקבלה שאלה חדשה בקורס '{data.course_name}' מאת {data.student_name} ({data.student_email}):\n\n"
            f"{data.body}\n"
        )

    _send_smtp_email(
        recipients=target_recipients,
        subject=email_subject,
        body=email_body,
        reply_to=data.student_email,
        use_bcc=False
    )

    return {
        "status": "success",
        "test_mode": bool(test_email),
        "delivered_to": target_recipients[0],
        "intended_lecturer": real_recipient_email
    }


@dashboard_router.post("/emails/broadcast")
async def broadcast_email_to_students(data: LecturerBroadcastEmail):
    if not data.subject.strip() or not data.body.strip():
        raise HTTPException(status_code=400, detail="נא למלא נושא ותוכן להודעה")

    conn = get_db_connection()
    cursor = conn.cursor()
    _ensure_tables(cursor)

    lecturer_email = _get_course_lecturer_email(cursor, data.course_name)

    cursor.execute(
        "SELECT DISTINCT student_email FROM course_students WHERE course_name = ? AND student_email LIKE '%@%'",
        (data.course_name,)
    )
    real_students = sorted([row["student_email"].strip().lower() for row in cursor.fetchall()])
    conn.close()

    test_email = os.getenv("TEST_EMAIL", "").strip()

    if test_email:
        target_recipients = [test_email]
        students_preview = ", ".join(real_students) if real_students else "לא הועלה עדיין קובץ אקסל לקורס זה"
        email_subject = f"[בדיקה -> {len(real_students)} סטודנטים] [{data.course_name}] {data.subject}"
        email_body = (
            f"מצב בדיקה (TEST_EMAIL): מייל זה היה נשלח בשם המרצה ({lecturer_email}) ב-BCC אל {len(real_students)} סטודנטים בקורס '{data.course_name}':\n"
            f"רשימת נמענים מקורית: {students_preview}\n"
            f"--------------------------------------------------\n\n"
            f"{data.body}\n"
        )
    else:
        if not real_students:
            raise HTTPException(status_code=400, detail="לא נמצאו סטודנטים בקורס זה. העלה תחילה קובץ Excel בלשונית הסטודנטים.")
        target_recipients = real_students
        email_subject = f"[{data.course_name}] {data.subject}"
        email_body = f"הודעה מאת מרצה הקורס ({lecturer_email}):\n\n{data.body}\n"

    _send_smtp_email(
        recipients=target_recipients,
        subject=email_subject,
        body=email_body,
        reply_to=lecturer_email,
        use_bcc=not bool(test_email)
    )

    return {
        "status": "success",
        "test_mode": bool(test_email),
        "delivered_to": test_email if test_email else f"{len(real_students)} סטודנטים",
        "students_count": len(real_students)
    }