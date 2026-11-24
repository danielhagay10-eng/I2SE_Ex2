import io
import sqlite3
from types import SimpleNamespace
import openpyxl
import pytest
from fastapi.testclient import TestClient

import server
import main
import dashboard_api
import student
import lecturer


def _build_excel_bytes(headers: list[str], rows: list[list[str]]) -> io.BytesIO:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(headers)
    for row in rows:
        ws.append(row)
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf


@pytest.fixture()
def client(tmp_path, monkeypatch):
    test_db_path = tmp_path / "test_attendance.db"

    def _test_db_conn():
        conn = sqlite3.connect(str(test_db_path))
        conn.row_factory = sqlite3.Row
        return conn

    for mod in (server, main, dashboard_api, student, lecturer):
        if hasattr(mod, "get_db_connection"):
            monkeypatch.setattr(mod, "get_db_connection", _test_db_conn)

    monkeypatch.chdir(tmp_path)
    server.init_db()

    monkeypatch.setenv("ADMIN_USERNAME", "admin")
    monkeypatch.setenv("ADMIN_PASSWORD", "StrongAdminPass2026!")
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "test-google-client-id.apps.googleusercontent.com")
    monkeypatch.setenv("ENABLE_DEMO_LOGIN", "true")
    monkeypatch.setenv("DEMO_LECTURER_EMAIL", "demo.lecturer@smartlms.local")
    monkeypatch.setenv("DEMO_STUDENT_EMAIL", "demo.student@smartlms.local")
    monkeypatch.delenv("TEST_EMAIL", raising=False)

    return TestClient(main.app)


def test_admin_excel_and_google_oauth_role_resolution(client, monkeypatch):
    bad_login = client.post("/api/admin/login", json={"username": "admin", "password": "wrong"})
    assert bad_login.status_code == 401

    ok_login = client.post("/api/admin/login", json={"username": "admin", "password": "StrongAdminPass2026!"})
    assert ok_login.status_code == 200
    headers = {"X-Admin-Token": ok_login.json()["token"]}

    lec_excel = _build_excel_bytes(
        ["שם מלא", "כתובת דוא\"ל"],
        [["ד\"ר ישראל ישראלי", "prof.israel@ariel.ac.il"]]
    )
    upload_res = client.post(
        "/api/admin/lecturers/upload-excel",
        headers=headers,
        files={"file": ("lecturers.xlsx", lec_excel, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
    )
    assert upload_res.status_code == 200
    assert upload_res.json()["imported_count"] == 1

    fake_tokens = {
        "valid_lecturer_token": {
            "aud": "test-google-client-id.apps.googleusercontent.com",
            "email": "prof.israel@ariel.ac.il",
            "given_name": "ישראל",
            "family_name": "ישראלי"
        },
        "valid_student_token": {
            "aud": "test-google-client-id.apps.googleusercontent.com",
            "email": "dana.levi@gmail.com",
            "given_name": "דנה",
            "family_name": "לוי"
        },
        "wrong_aud_token": {
            "aud": "other-app.apps.googleusercontent.com",
            "email": "hacker@gmail.com"
        }
    }

    def _mock_google_verify(id_token: str) -> dict:
        if id_token not in fake_tokens:
            raise ValueError("Invalid token")
        return fake_tokens[id_token]

    monkeypatch.setattr(main, "_fetch_google_token_info", _mock_google_verify)

    lec_res = client.post("/auth/google", json={"token": "valid_lecturer_token"})
    assert lec_res.status_code == 200
    assert lec_res.json()["role"] == "lecturer"
    assert lec_res.json()["email"] == "prof.israel@ariel.ac.il"

    stu_res = client.post("/auth/google", json={"token": "valid_student_token"})
    assert stu_res.status_code == 200
    assert stu_res.json()["role"] == "student"

    assert client.post("/auth/google", json={"token": "wrong_aud_token"}).status_code == 401
    assert client.post("/auth/google", json={"token": "expired_or_bad"}).status_code == 401
    assert client.post("/login", json={"user_id": "prof.israel@ariel.ac.il"}).status_code == 404


def test_secure_demo_login_and_impersonation_block(client, monkeypatch):
    lec_demo = client.post("/auth/mock-login", json={"demo_type": "lecturer"})
    assert lec_demo.status_code == 200
    assert lec_demo.json()["role"] == "lecturer"
    assert lec_demo.json()["email"] == "demo.lecturer@smartlms.local"

    stu_demo = client.post("/auth/mock-login", json={"demo_type": "student"})
    assert stu_demo.status_code == 200
    assert stu_demo.json()["role"] == "student"

    conn = server.get_db_connection()
    cur = conn.cursor()
    cur.execute("INSERT INTO approved_lecturers (email, full_name, added_at) VALUES ('real.prof@ariel.ac.il', 'מרצה אמיתי', '24/11/2026')")
    conn.commit()
    conn.close()

    monkeypatch.setenv("DEMO_LECTURER_EMAIL", "real.prof@ariel.ac.il")
    assert client.post("/auth/mock-login", json={"demo_type": "lecturer"}).status_code == 403


def test_course_lifecycle_rename_delete_and_student_dashboard(client):
    lec = "prof@ariel.ac.il"

    create_res = client.post("/api/lecturer/courses", json={"course_name": "מבוא לחישוב", "lecturer_id": lec})
    assert create_res.status_code == 200
    course_obj = create_res.json()["course"]
    cid = course_obj["id"]
    orig_date = course_obj["created_at"]
    assert len(orig_date) == 10

    roster_excel = _build_excel_bytes(
        ["שם פרטי", "שם משפחה", "כתובת דוא\"ל", "תפקידים"],
        [
            ["דנה", "לוי", "dana@ariel.ac.il", "סטודנט"],
            ["רועי", "מתרגל", "ta.roy@ariel.ac.il", "מתרגל"]
        ]
    )
    up = client.post(
        "/api/course/students/upload-excel",
        data={"course_name": "מבוא לחישוב"},
        files={"file": ("roster.xlsx", roster_excel, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
    )
    assert up.status_code == 200
    assert up.json()["imported_count"] == 1
    assert up.json()["staff_imported_count"] == 1

    assert len(client.get("/api/student/courses?student_email=dana@ariel.ac.il").json()["courses"]) == 1
    assert len(client.get("/api/student/courses?student_email=yossi@ariel.ac.il").json()["courses"]) == 0

    ren = client.put(f"/api/lecturer/courses/{cid}", json={"course_name": "מבוא למדעי המחשב", "lecturer_id": lec})
    assert ren.status_code == 200
    assert ren.json()["created_at"] == orig_date

    dana_courses = client.get("/api/student/courses?student_email=dana@ariel.ac.il").json()["courses"]
    assert dana_courses[0]["course_name"] == "מבוא למדעי המחשב"
    assert dana_courses[0]["created_at"] == orig_date

    dele = client.delete(f"/api/lecturer/courses/{cid}?lecturer_id={lec}")
    assert dele.status_code == 200
    assert len(client.get("/api/student/courses?student_email=dana@ariel.ac.il").json()["courses"]) == 0


def test_dual_role_lecturer_student_and_deleted_course_guard(client):
    prof_a = "prof.a@ariel.ac.il"
    prof_b = "prof.b@ariel.ac.il"

    # 1. מרצה א' פותח קורס משלו, ומרצה ב' פותח קורס ומכניס את מרצה א' כסטודנט
    c_a = client.post("/api/lecturer/courses", json={"course_name": "אלגוריתמים", "lecturer_id": prof_a}).json()["course"]
    client.post("/api/lecturer/courses", json={"course_name": "מבני נתונים", "lecturer_id": prof_b})

    roster_b = _build_excel_bytes(
        ["שם פרטי", "שם משפחה", "כתובת דוא\"ל"],
        [["מרצה", "אלף", prof_a]]
    )
    up_res = client.post(
        "/api/course/students/upload-excel",
        data={"course_name": "מבני נתונים"},
        files={"file": ("roster_b.xlsx", roster_b, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
    )
    assert up_res.status_code == 200

    # 2. מרצה א' רואה את "אלגוריתמים" כמרצה, ואת "מבני נתונים" כסטודנט
    as_lec = client.get(f"/api/lecturer/courses?lecturer_id={prof_a}").json()["courses"]
    assert [c["course_name"] for c in as_lec] == ["אלגוריתמים"]

    as_stu = client.get(f"/api/student/courses?student_email={prof_a}").json()["courses"]
    assert [c["course_name"] for c in as_stu] == ["מבני נתונים"]

    # 3. בדיקת נתיב קיום הקורס לפני ואחרי מחיקה (מונע חזרה בדפדפן לקורס מחוק)
    assert client.get("/api/courses/exists?course_name=אלגוריתמים").json()["exists"] is True

    del_res = client.delete(f"/api/lecturer/courses/{c_a['id']}?lecturer_id={prof_a}")
    assert del_res.status_code == 200
    assert client.get("/api/courses/exists?course_name=אלגוריתמים").json()["exists"] is False


def test_qr_enrollment_enforcement_and_controlled_demo(client):
    c_real = client.post("/api/lecturer/courses", json={"course_name": "אלגברה", "lecturer_id": "prof@ariel.ac.il"}).json()["course"]
    c_demo = client.post("/api/lecturer/courses", json={"course_name": "קורס הדגמה", "lecturer_id": "demo.lecturer@smartlms.local"}).json()["course"]

    conn = server.get_db_connection()
    cur = conn.cursor()
    cur.execute("INSERT INTO course_students (course_name, student_email, full_name) VALUES ('אלגברה', 'dana@ariel.ac.il', 'דנה לוי')")
    cur.execute("INSERT INTO sessions (course_id, token, status) VALUES (?, 'REAL_TOK', 'active')", (c_real["id"],))
    cur.execute("INSERT INTO sessions (course_id, token, status) VALUES (?, 'DEMO_TOK', 'active')", (c_demo["id"],))
    conn.commit()
    conn.close()

    unauth = client.post("/student/mark_attendance", json={
        "session_id": "REAL_TOK", "student_id": "stranger@ariel.ac.il", "first_name": "זר", "last_name": "אחד"
    })
    assert unauth.status_code == 403

    demo_to_real = client.post("/student/mark_attendance", json={
        "session_id": "REAL_TOK", "student_id": "demo.student@smartlms.local", "first_name": "סטודנט", "last_name": "דמו"
    })
    assert demo_to_real.status_code == 403

    demo_to_demo = client.post("/student/mark_attendance", json={
        "session_id": "DEMO_TOK", "student_id": "demo.student@smartlms.local", "first_name": "סטודנט", "last_name": "דמו"
    })
    assert demo_to_demo.status_code == 200

    ok_stu = client.post("/student/mark_attendance", json={
        "session_id": "REAL_TOK", "student_id": "dana@ariel.ac.il", "first_name": "דנה", "last_name": "לוי"
    })
    assert ok_stu.status_code == 200


def test_staff_recipient_selection_and_emails(client, monkeypatch):
    course = "מערכות ספרתיות"
    sent_emails = []

    def _fake_smtp(recipients, subject, body, reply_to=None, use_bcc=False):
        sent_emails.append({"recipients": recipients, "reply_to": reply_to, "use_bcc": use_bcc})

    monkeypatch.setattr(dashboard_api, "_send_smtp_email", _fake_smtp)

    client.post("/api/lecturer/courses", json={"course_name": course, "lecturer_id": "prof@ariel.ac.il"})
    client.post("/api/course/staff", json={
        "course_name": course, "staff_email": "ta@ariel.ac.il", "full_name": "מתרגל הקורס", "role_title": "מתרגל"
    })

    staff = client.get(f"/api/course/staff?course_name={course}").json()["staff"]
    assert len(staff) == 2

    ask = client.post("/api/emails/ask-lecturer", json={
        "course_name": course,
        "student_email": "s1@ariel.ac.il",
        "student_name": "סטודנט 1",
        "recipient_email": "ta@ariel.ac.il",
        "subject": "שאלה בתרגיל בית",
        "body": "שלום, אשמח להבהרה."
    })
    assert ask.status_code == 200
    assert sent_emails[-1]["recipients"] == ["ta@ariel.ac.il"]
    assert sent_emails[-1]["reply_to"] == "s1@ariel.ac.il"


def test_lesson_ai_summary_and_cache(client, monkeypatch):
    course = "מבני נתונים"
    lesson_res = client.post(
        "/api/lessons/with-files",
        data={"course_name": course, "title": "עצי AVL", "date_str": "24/11/2026"},
        files=[("files", ("avl_notes.txt", io.BytesIO(b"AVL balance factor is -1, 0, or 1"), "text/plain"))]
    )
    assert lesson_res.status_code == 200
    lesson_id = lesson_res.json()["id"]

    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    no_key = client.post(f"/api/lessons/{lesson_id}/summarize")
    assert no_key.status_code == 500

    stats = {"uploads": 0, "deletes": 0, "generations": 0}

    class _FakeGenAIClient:
        def __init__(self, api_key):
            self.files = SimpleNamespace(
                upload=self._upload,
                get=lambda name: SimpleNamespace(name=name, state=SimpleNamespace(name="ACTIVE")),
                delete=self._delete
            )
            self.models = SimpleNamespace(
                list=lambda: [],
                generate_content=self._generate
            )

        def _upload(self, file):
            stats["uploads"] += 1
            return SimpleNamespace(name="files/mock_avl", state=SimpleNamespace(name="ACTIVE"))

        def _delete(self, name):
            stats["deletes"] += 1

        def _generate(self, model, contents):
            stats["generations"] += 1
            return SimpleNamespace(text="סיכום עצי AVL: הפרש הגבהים בין תת-עץ שמאלי לימני הוא לכל היותר 1.")

    monkeypatch.setenv("GEMINI_API_KEY", "fake-gemini-key")
    monkeypatch.setattr(dashboard_api.genai, "Client", _FakeGenAIClient)

    first_call = client.post(f"/api/lessons/{lesson_id}/summarize")
    assert first_call.status_code == 200
    assert first_call.json()["cached"] is False
    assert "AVL" in first_call.json()["summary"]
    assert stats == {"uploads": 1, "deletes": 1, "generations": 1}

    second_call = client.post(f"/api/lessons/{lesson_id}/summarize")
    assert second_call.status_code == 200
    assert second_call.json()["cached"] is True
    assert second_call.json()["summary"] == first_call.json()["summary"]
    assert stats["generations"] == 1