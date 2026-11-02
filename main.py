from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from server import init_db
from student import student_router
from lecturer import lecturer_router

# איתחול מסד הנתונים
init_db()

# יצירת אפליקציית השרת
app = FastAPI(title="Teaching Tool API")

# הגדרת CORS כדי לאפשר לדף ה-HTML לתקשר עם השרת בלי חסימות
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # מאפשר לכל כתובת (כמו Live Server) להתחבר
    allow_credentials=True,
    allow_methods=["*"],  # מאפשר את כל סוגי הבקשות (GET, POST וכו')
    allow_headers=["*"],
)

# חיבור הקבצים (הראוטרים) של התלמיד והמרצה
app.include_router(student_router)
app.include_router(lecturer_router)
from pydantic import BaseModel
from fastapi import HTTPException
from server import get_db_connection

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

@app.get("/")
def read_root():
    return {"message": "Welcome to the Web-based Teaching Tool"}