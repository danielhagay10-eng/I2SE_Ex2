from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

# ייבוא מהקבצים שלך
from server import init_db, get_db_connection
from student import student_router
from lecturer import lecturer_router

# איתחול מסד הנתונים
init_db()

# יצירת אפליקציית השרת
app = FastAPI(title="Teaching Tool API")

# הגדרת תיקיית ה-HTML למסך ההתחברות
templates = Jinja2Templates(directory="templates")

# הגדרת CORS כדי לאפשר לדף ה-HTML לתקשר עם השרת בלי חסימות
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- נתיב דף הבית: מציג את מסך ההתחברות של גוגל ---
# --- נתיבי תצוגה (HTML) ---

@app.get("/")
async def serve_login_page(request: Request):
    # מציג את מסך ההתחברות הראשי (עם תעודת הזהות)
    return templates.TemplateResponse(request, "login.html")

@app.get("/google-login")
async def serve_google_login(request: Request):
    # למקרה שתרצה להשתמש במסך של גוגל
    return templates.TemplateResponse(request, "index.html")

@app.get("/lecturer.html")
async def serve_lecturer_dashboard(request: Request):
    # כשהדפדפן מבקש את מסך המרצה, נטען את הקובץ שלך
    return templates.TemplateResponse(request, "dashboard.html")

@app.get("/course_dashboard.html")
async def serve_course_dashboard(request: Request):
    # המסך השלישי שיצרנו (לניהול קורס ספציפי)
    return templates.TemplateResponse(request, "course_dashboard.html")
@app.get("/student_dashboard.html")
async def serve_student_dashboard(request: Request):
    return templates.TemplateResponse(request, "student_dashboard.html")
# --- נתיב ההתחברות הקיים שלך ---
class LoginRequest(BaseModel):
    user_id: str

@app.post("/login")
async def login(data: LoginRequest):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # חיפוש המשתמש במסד הנתונים
    cursor.execute("SELECT role, first_name FROM users WHERE id = ?", (data.user_id,))
    user = cursor.fetchone()
    conn.close()
    
    if not user:
        raise HTTPException(status_code=404, detail="משתמש לא נמצא במערכת")
        
    return {"status": "success", "role": user['role'], "name": user['first_name']}

# חיבור הקבצים (הראוטרים) של התלמיד והמרצה
app.include_router(student_router)
app.include_router(lecturer_router)

class GoogleTokenRequest(BaseModel):
    token: str

@app.post("/auth/google")
async def verify_google_token(data: GoogleTokenRequest):
    # בשלב הבא נוסיף כאן פענוח אמיתי של הטוקן מול גוגל ושליפה מה-DB
    print("Received Google Token in Backend!")
    
    # כרגע אנחנו מחזירים תשובה קבועה רק כדי לראות שהמעבר לדשבורד עובד
    # אפשר לשנות את ה-role ל-"student" כדי לבדוק את המסך השני
    return {
        "status": "success", 
        "role": "lecturer", 
        "name": "דניאל"
    }
@app.get("/live_session.html")
async def serve_live_session(request: Request):
 return templates.TemplateResponse(request, "lecturer.html")