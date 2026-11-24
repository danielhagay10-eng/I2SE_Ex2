from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, Request, HTTPException, UploadFile, File, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import Optional
from datetime import datetime
import urllib.request
import urllib.parse
import hashlib
import json
import os

from server import init_db, get_db_connection
from student import student_router
from lecturer import lecturer_router
from dashboard_api import dashboard_router

init_db()

app = FastAPI(title="SmartLMS API")
os.makedirs("uploads", exist_ok=True)
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

templates = Jinja2Templates(directory="templates")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def disable_browser_cache(request: Request, call_next):
    """מונע שמירת עמודים ונתוני API בזיכרון המטמון של הדפדפן בעת לחיצה על כפתור 'חזור'."""
    response = await call_next(request)
    if not request.url.path.startswith("/uploads"):
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
    return response


def _get_admin_credentials():
    username = os.getenv("ADMIN_USERNAME", "admin").strip()
    password = os.getenv("ADMIN_PASSWORD", "123456").strip()
    return username, password


def _make_admin_token(username: str, password: str) -> str:
    return hashlib.sha256(f"{username}:{password}:teaching_tool_admin".encode("utf-8")).hexdigest()


def _verify_admin_header(x_admin_token: Optional[str]):
    username, password = _get_admin_credentials()
    expected = _make_admin_token(username, password)
    if not x_admin_token or x_admin_token != expected:
        raise HTTPException(status_code=401, detail="אין הרשאת מנהל — נא להתחבר מחדש")


def _fetch_google_token_info(id_token: str) -> dict:
    verify_url = f"https://oauth2.googleapis.com/tokeninfo?id_token={urllib.parse.quote(id_token)}"
    with urllib.request.urlopen(verify_url, timeout=10) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _resolve_role_and_sync_user(cursor, email: str, first_name: str, last_name: str) -> tuple[str, str]:
    clean_email = email.strip().lower()
    cursor.execute("SELECT full_name FROM approved_lecturers WHERE LOWER(email) = ?", (clean_email,))
    lec_row = cursor.fetchone()

    role = "lecturer" if lec_row else "student"

    if lec_row and lec_row["full_name"]:
        full_name = lec_row["full_name"].strip()
    else:
        cursor.execute("SELECT full_name FROM course_students WHERE LOWER(student_email) = ? LIMIT 1", (clean_email,))
        st_row = cursor.fetchone()
        if st_row and st_row["full_name"]:
            full_name = st_row["full_name"].strip()
        else:
            full_name = f"{first_name} {last_name}".strip() or clean_email.split("@")[0]

    parts = full_name.split(" ", 1)
    db_first = parts[0]
    db_last = parts[1] if len(parts) > 1 else ""

    cursor.execute("SELECT id FROM users WHERE LOWER(id) = ?", (clean_email,))
    if cursor.fetchone():
        cursor.execute(
            "UPDATE users SET role = ?, first_name = ?, last_name = ? WHERE LOWER(id) = ?",
            (role, db_first, db_last, clean_email)
        )
    else:
        cursor.execute(
            "INSERT INTO users (id, first_name, last_name, role) VALUES (?, ?, ?, ?)",
            (clean_email, db_first, db_last, role)
        )

    return role, full_name


# --- נתיבי תצוגה (HTML) ---
@app.get("/")
async def serve_login_page(request: Request):
    return templates.TemplateResponse(
        request,
        "index.html",
        {"google_client_id": os.getenv("GOOGLE_CLIENT_ID", "").strip()}
    )


@app.get("/google-login")
async def serve_google_login(request: Request):
    return templates.TemplateResponse(
        request,
        "index.html",
        {"google_client_id": os.getenv("GOOGLE_CLIENT_ID", "").strip()}
    )


@app.get("/admin")
async def serve_admin_page(request: Request):
    return templates.TemplateResponse(request, "admin.html")


@app.get("/lecturer.html")
async def serve_lecturer_dashboard(request: Request):
    return templates.TemplateResponse(request, "dashboard.html")


@app.get("/course_dashboard.html")
async def serve_course_dashboard(request: Request):
    return templates.TemplateResponse(request, "course_dashboard.html")


@app.get("/student_dashboard.html")
async def serve_student_dashboard(request: Request):
    return templates.TemplateResponse(request, "student_dashboard.html")


@app.get("/live_session.html")
async def serve_live_session(request: Request):
    return templates.TemplateResponse(request, "lecturer.html")


@app.get("/student.html")
async def serve_student_live(request: Request):
    return templates.TemplateResponse(request, "student.html")


# --- 1. התחברות אמיתית באמצעות Google OAuth ---
class GoogleTokenRequest(BaseModel):
    token: str


@app.post("/auth/google")
async def verify_google_token(data: GoogleTokenRequest):
    if not data.token:
        raise HTTPException(status_code=400, detail="חסר טוקן אימות של Google")

    try:
        token_info = _fetch_google_token_info(data.token)
    except Exception:
        raise HTTPException(status_code=401, detail="אימות חשבון Google נכשל או שפג תוקף ההתחברות")

    expected_client_id = os.getenv("GOOGLE_CLIENT_ID", "").strip()
    if expected_client_id and token_info.get("aud") != expected_client_id:
        raise HTTPException(status_code=401, detail="מזהה אפליקציית Google אינו תואם")

    email = (token_info.get("email") or "").strip().lower()
    if not email:
        raise HTTPException(status_code=400, detail="לא התקבלה כתובת אימייל מחשבון Google")

    first_name = (token_info.get("given_name") or email.split("@")[0]).strip()
    last_name = (token_info.get("family_name") or "").strip()

    conn = get_db_connection()
    cursor = conn.cursor()
    role, full_name = _resolve_role_and_sync_user(cursor, email, first_name, last_name)
    conn.commit()
    conn.close()

    return {
        "status": "success",
        "role": role,
        "name": full_name,
        "email": email
    }


# --- 2. התחברות דמו סגורה ומאובטחת ---
class MockLoginRequest(BaseModel):
    demo_type: str


@app.post("/auth/mock-login")
async def mock_login(data: MockLoginRequest):
    if os.getenv("ENABLE_DEMO_LOGIN", "true").strip().lower() != "true":
        raise HTTPException(status_code=403, detail="מצב דמו כבוי במערכת")

    if data.demo_type == "lecturer":
        email = os.getenv("DEMO_LECTURER_EMAIL", "demo.lecturer@smartlms.local").strip().lower()
        full_name = "מרצה דמו"
        role = "lecturer"
    elif data.demo_type == "student":
        email = os.getenv("DEMO_STUDENT_EMAIL", "demo.student@smartlms.local").strip().lower()
        full_name = "סטודנט דמו"
        role = "student"
    else:
        raise HTTPException(status_code=400, detail="סוג משתמש דמו לא תקין")

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT 1 FROM approved_lecturers WHERE LOWER(email) = ?", (email,))
    if cursor.fetchone():
        conn.close()
        raise HTTPException(status_code=403, detail="אין להתחבר לחשבון מרצה אמיתי דרך מצב דמו — השתמש בהתחברות Google")

    parts = full_name.split(" ", 1)
    cursor.execute(
        """INSERT INTO users (id, first_name, last_name, role)
           VALUES (?, ?, ?, ?)
           ON CONFLICT(id) DO UPDATE SET role = excluded.role, first_name = excluded.first_name, last_name = excluded.last_name""",
        (email, parts[0], parts[1] if len(parts) > 1 else "", role)
    )
    conn.commit()
    conn.close()

    return {
        "status": "success",
        "role": role,
        "name": full_name,
        "email": email
    }


# --- 3. ממשק מנהל מערכת (Admin) ---
class AdminLoginRequest(BaseModel):
    username: str
    password: str


class ManualLecturerRequest(BaseModel):
    email: str
    full_name: Optional[str] = ""


@app.post("/api/admin/login")
async def admin_login(data: AdminLoginRequest):
    expected_user, expected_pass = _get_admin_credentials()
    if data.username.strip() != expected_user or data.password.strip() != expected_pass:
        raise HTTPException(status_code=401, detail="שם משתמש או סיסמה שגויים")

    return {
        "status": "success",
        "token": _make_admin_token(expected_user, expected_pass)
    }


@app.get("/api/admin/lecturers")
async def get_approved_lecturers(x_admin_token: Optional[str] = Header(None)):
    _verify_admin_header(x_admin_token)
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT email, full_name, added_at FROM approved_lecturers ORDER BY full_name ASC")
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return {"lecturers": rows}


@app.post("/api/admin/lecturers/upload-excel")
async def upload_lecturers_excel(
    file: UploadFile = File(...),
    x_admin_token: Optional[str] = Header(None)
):
    _verify_admin_header(x_admin_token)

    if not file.filename.lower().endswith((".xlsx", ".xlsm")):
        raise HTTPException(status_code=400, detail="נא להעלות קובץ Excel תקין בפורמט .xlsx")

    try:
        import openpyxl
    except ImportError:
        raise HTTPException(status_code=500, detail="חסרה הספרייה openpyxl. הרץ: pip install openpyxl")

    wb = openpyxl.load_workbook(file.file, data_only=True)
    ws = wb.active
    rows = list(ws.iter_rows(values_only=True))
    if not rows:
        raise HTTPException(status_code=400, detail="קובץ האקסל ריק")

    first_row_strs = [str(c).strip().lower() if c is not None else "" for c in rows[0]]
    has_header = not any("@" in cell for cell in first_row_strs)

    email_idx = None
    first_idx = None
    last_idx = None
    full_idx = None
    data_rows = rows[1:] if has_header else rows

    if has_header:
        def find_col(candidates):
            for idx, h in enumerate(first_row_strs):
                for c in candidates:
                    if c == h or c in h:
                        return idx
            return None

        email_idx = find_col(['כתובת דוא"ל', 'כתובת דוא״ל', 'דוא"ל', 'אימייל', 'מייל', 'email', 'e-mail'])
        first_idx = find_col(['שם פרטי', 'first name', 'firstname'])
        last_idx = find_col(['שם משפחה', 'last name', 'lastname', 'surname'])
        full_idx = find_col(['שם מלא', 'full name', 'fullname', 'name', 'שם מרצה', 'שם'])

    lecturers = {}
    for r in data_rows:
        if not r or all(v is None or str(v).strip() == "" for v in r):
            continue

        raw_email = ""
        if email_idx is not None and email_idx < len(r) and r[email_idx] is not None:
            raw_email = str(r[email_idx]).strip().lower()
        else:
            for cell in r:
                if cell is not None and "@" in str(cell):
                    raw_email = str(cell).strip().lower()
                    break

        if "@" not in raw_email:
            continue

        first_name = str(r[first_idx]).strip() if (first_idx is not None and first_idx < len(r) and r[first_idx] is not None) else ""
        last_name = str(r[last_idx]).strip() if (last_idx is not None and last_idx < len(r) and r[last_idx] is not None) else ""

        if first_name or last_name:
            full_name = f"{first_name} {last_name}".strip()
        elif full_idx is not None and full_idx < len(r) and r[full_idx] is not None:
            full_name = str(r[full_idx]).strip()
        else:
            full_name = raw_email.split("@")[0]

        lecturers[raw_email] = full_name

    if not lecturers:
        raise HTTPException(status_code=400, detail="לא נמצאו כתובות מייל תקינות של מרצים בקובץ האקסל")

    conn = get_db_connection()
    cursor = conn.cursor()
    now_str = datetime.now().strftime("%d/%m/%Y %H:%M")

    cursor.execute("DELETE FROM approved_lecturers")
    for email, full_name in lecturers.items():
        cursor.execute(
            "INSERT INTO approved_lecturers (email, full_name, added_at) VALUES (?, ?, ?)",
            (email, full_name, now_str)
        )
        parts = full_name.split(" ", 1)
        cursor.execute(
            """INSERT INTO users (id, first_name, last_name, role)
               VALUES (?, ?, ?, 'lecturer')
               ON CONFLICT(id) DO UPDATE SET role = 'lecturer', first_name = excluded.first_name, last_name = excluded.last_name""",
            (email, parts[0], parts[1] if len(parts) > 1 else "")
        )

    placeholders = ",".join("?" for _ in lecturers)
    cursor.execute(
        f"UPDATE users SET role = 'student' WHERE LOWER(id) NOT IN ({placeholders})",
        list(lecturers.keys())
    )

    conn.commit()
    conn.close()
    return {"status": "success", "imported_count": len(lecturers)}


@app.post("/api/admin/lecturers/add")
async def add_single_lecturer(
    data: ManualLecturerRequest,
    x_admin_token: Optional[str] = Header(None)
):
    _verify_admin_header(x_admin_token)
    email = data.email.strip().lower()
    if "@" not in email:
        raise HTTPException(status_code=400, detail="נא להזין כתובת מייל תקינה")

    full_name = (data.full_name or "").strip() or email.split("@")[0]
    now_str = datetime.now().strftime("%d/%m/%Y %H:%M")

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT OR REPLACE INTO approved_lecturers (email, full_name, added_at) VALUES (?, ?, ?)",
        (email, full_name, now_str)
    )
    parts = full_name.split(" ", 1)
    cursor.execute(
        """INSERT INTO users (id, first_name, last_name, role)
           VALUES (?, ?, ?, 'lecturer')
           ON CONFLICT(id) DO UPDATE SET role = 'lecturer', first_name = excluded.first_name, last_name = excluded.last_name""",
        (email, parts[0], parts[1] if len(parts) > 1 else "")
    )
    conn.commit()
    conn.close()
    return {"status": "success"}


@app.delete("/api/admin/lecturers/{email}")
async def remove_lecturer(email: str, x_admin_token: Optional[str] = Header(None)):
    _verify_admin_header(x_admin_token)
    clean_email = email.strip().lower()

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM approved_lecturers WHERE LOWER(email) = ?", (clean_email,))
    cursor.execute("UPDATE users SET role = 'student' WHERE LOWER(id) = ?", (clean_email,))
    conn.commit()
    conn.close()
    return {"status": "deleted"}


app.include_router(student_router)
app.include_router(lecturer_router)
app.include_router(dashboard_router)