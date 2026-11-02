# 🛠️ Technical-Related Tools Report

This report outlines the technical tools, libraries, and external APIs selected to build the Web-based Teaching Tool demo. Following the *Vibe Coding* philosophy, the selected stack emphasizes rapid composition, integration of powerful AI models, and minimizing custom code. All tools have been tested in real-world scenarios for feasibility.

## 1. Backend & Server Infrastructure
*   **FastAPI (Python):** 
    *   *Purpose:* To serve as the core backend API, handling requests from the web app, routing AI prompts, and managing data.
    *   *Why:* Extremely fast to develop, built-in Swagger UI for instant API testing, and native integration with Python’s AI and data processing ecosystems.
*   **SQLite (Local Database):**
    *   *Purpose:* To store user data (lecturers/students), course details, attendance logs, and real-time question queues.
    *   *Why:* Zero-configuration, serverless, and perfect for a localized 10-minute demo without network overhead.

## 2. Frontend (Web Application)
*   **HTML / CSS / Vanilla JavaScript:**
    *   *Purpose:* To build the responsive user interface for both the lecturer dashboard and the student smartphone app.
    *   *Why:* Keeps the project adhering strictly to the KISS principle. No need for complex build steps or heavy frameworks like React for a simple demo.
*   **qrcode.js & html5-qrcode:**
    *   *Purpose:* `qrcode.js` dynamically generates the attendance QR code on the lecturer's screen. `html5-qrcode` accesses the student's smartphone camera to scan it.
    *   *Testing Result:* Successfully tested generating dynamic tokens and reading them via a mobile browser without native app installation.

## 3. Artificial Intelligence & LLM Integrations
*   **OpenAI GPT-4o / Gemini 1.5 Pro API (Vision & Text):**
    *   *Vision (Headcount):* Used to analyze a photo of the classroom taken by the lecturer. The model counts the number of students to validate the QR scans (preventing proxy attendance).
    *   *Text (Homework Review):* Used to analyze parsed PDF text against a grading rubric, returning structured JSON with error counts and feedback.
*   **OpenAI Whisper API:**
    *   *Purpose:* To transcribe uploaded audio/video files of the lecture into text, which is then summarized by the LLM into bullet points.

## 4. File Processing
*   **PyPDF2 (Python):**
    *   *Purpose:* To extract raw text from PDF homework submissions before sending the content to the LLM for evaluation.