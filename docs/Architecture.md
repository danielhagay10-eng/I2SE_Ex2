# 🏗️ Architecture & System Design

## 1. Main Use Cases (Client Stories)

*   **UC1: Automatic Attendance:** As a student, I want to scan a QR code displayed on the board using my smartphone so that my attendance is recorded instantly without calling names.
*   **UC2: AI Headcount Validation:** As a lecturer, I want to take a picture of the classroom so that the system can verify the physical headcount matches the digital QR scans (preventing cheating).
*   **UC3: Real-Time Question (Red Button):** As a student, I want to click a button and type a question that instantly pops up on the lecturer's screen without interrupting the class.
*   **UC4: Volunteer to Answer (Green Button):** As a lecturer, I want to see a live list of students willing to answer my verbal question, so I can pick one easily.
*   **UC5: AI Video Summary:** As a student, I want to read a structured summary of a recorded lecture so I can review the material efficiently.

## 2. Main Software Components
1.  **Student Web App (Client):** Mobile-first UI containing the QR scanner, course list, and real-time interaction buttons.
2.  **Lecturer Dashboard (Client):** Desktop UI for managing sessions, generating QR tokens, viewing question queues, and uploading files.
3.  **FastAPI Core Server (Backend):** Manages API routes, handles state (active class vs. closed class), and communicates with the database.
4.  **AI Orchestrator (Backend Module):** A dedicated Python module that formats prompts and handles external API calls to OpenAI/Gemini (Whisper, Vision, Text).
5.  **SQLite Database:** Stores persistent data (Users, Courses, Attendance Logs, Questions).

## 3. UML Diagrams (Conceptual)

### 3.1 Low-Level Class Diagram
*(To be generated visually via Draw.io/PlantUML. Below is the structural representation)*
*   `User` (Base) -> `Lecturer`, `Student`
*   `Course` (Contains list of Students and Sessions)
*   `Session` (Manages active state, holds `AttendanceRecord` and `QuestionQueue`)
*   `LLMService` (Interface for `VisionHeadcount`, `VideoSummarizer`, `HomeworkGrader`)

### 3.2 Sequence Diagram: Attendance Flow
1.  `Lecturer` clicks "Open Session".
2.  `Server` generates a unique `SessionToken` and returns it.
3.  `Lecturer Dashboard` displays the Token as a QR code.
4.  `Student` scans the QR and sends `POST /attendance {token, student_id}`.
5.  `Server` validates Token and updates `Database`.
6.  `Lecturer` uploads a photo via `POST /verify_headcount`.
7.  `Server` sends photo to `AI Vision API`.
8.  `AI Vision API` returns integer (headcount).
9.  `Server` compares integer to database count and alerts `Lecturer`.