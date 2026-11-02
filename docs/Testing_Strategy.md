# 🧪 Testing Strategy

Given the rapid development cycle (Vibe Coding) and the strict 10-minute demo constraint, the testing strategy focuses on critical path validation, integration points, and UI responsiveness.

## 1. Unit Testing (Class Level)
*   **Session Management (`Session` Class):** 
    *   Verify that QR tokens are generated correctly and expire after the designated time.
    *   Verify state transitions (e.g., changing from "Active" to "Waiting for Answers").
*   **LLM Service Interface (`LLMService` Class):**
    *   Mock external API calls to ensure the server handles timeouts or malformed JSON responses from OpenAI/Gemini gracefully.
    *   Test the PDF parsing logic (`PyPDF2`) to ensure text is extracted cleanly before sending it to the LLM.

## 2. Integration Testing
*   **Database Connectivity:** Ensure the FastAPI server can accurately write attendance records and retrieve participation statistics from SQLite.
*   **Real-time Polling/WebSockets:** Verify that when the lecturer opens the "Green Button" prompt, the student UI updates within 3 seconds.

## 3. End-to-End (E2E) "Happy Path" Demo Testing
Before the live classroom demonstration, the following scenario must run flawlessly:
1.  Login as Lecturer and open a new session.
2.  Login as Student on a mobile device and scan the generated QR.
3.  Upload a dummy classroom photo and verify the AI headcount response.
4.  Trigger a "Red Button" question from the mobile device and verify the UI toast notification appears on the Lecturer's screen.
5.  Upload a small PDF homework file and verify the LLM generates a structured grade and error count.

## 4. UI / UX Testing
*   Verify the Student App is fully legible and usable on mobile screens (responsive design).
*   Ensure buttons (Red/Green) are large enough to prevent misclicks (Fat-finger testing).