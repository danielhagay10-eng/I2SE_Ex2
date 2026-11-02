from fastapi import FastAPI
from server import init_db
from student import student_router
from lecturer import lecturer_router

# איתחול מסד הנתונים
init_db()

# יצירת אפליקציית השרת
app = FastAPI(title="Teaching Tool API")

# חיבור הקבצים (הראוטרים) של התלמיד והמרצה
app.include_router(student_router)
app.include_router(lecturer_router)

@app.get("/")
def read_root():
    return {"message": "Welcome to the Web-based Teaching Tool"}