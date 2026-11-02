# 📑 Software Requirements Specification (SRS)

## 1. Introduction
### 1.1 Purpose
The purpose of this system is to provide a smart, simple, and highly interactive web-based teaching tool based on the KISS (Keep It Simple, Stupid) principle. The system replaces clunky manual processes with modern AI-driven tools (LLMs, Computer Vision) to enable automated attendance, live classroom interaction, lecture summaries, and AI-assisted grading.

### 1.2 Scope
The project is a responsive web application designed for mobile phones (students) and desktop computers (lecturers). It operates completely independently and requires **no integration** with external university systems (e.g., Moodle, Zoom, Personal Info Systems).

## 2. User Roles
*   **Master Admin:** Has privileges to open/close course registration, manage users, and define new courses.
*   **Lecturer:** Can open a live session, project a QR code, trigger live interactions (questions/volunteers), upload recordings for AI summaries, and review AI-graded homework.
*   **Student:** Can mark attendance via QR scan, participate in live sessions via quick-action buttons, view AI summaries, submit PDF homework, and view personal statistics.

## 3. Functional Requirements
### 3.1 Smart Attendance System
*   **REQ-1.1 (QR Generation):** The system shall generate a dynamic, unique QR code when a lecturer opens a session.
*   **REQ-1.2 (QR Scanning):** The student web app shall access the device camera to scan the QR code and record attendance.
*   **REQ-1.3 (AI Headcount):** The lecturer shall be able to upload a photo of the classroom. The system shall use an AI Vision API to count the students and alert the lecturer if the discrepancy is >5%.

### 3.2 Live Classroom Interaction
*   **REQ-2.1 (Red Button):** Students shall have a button to submit a text question. The system shall display this as a live toast notification on the lecturer's screen.
*   **REQ-2.2 (Green Button):** The lecturer shall be able to trigger a "Volunteer" mode. Students clicking the green button will populate a live list on the lecturer's screen.
*   **REQ-2.3 (Participation Tracking):** The system shall log student interactions (0, 1-2, 3+ times) for end-of-class statistics.

### 3.3 AI-Powered Summaries & Grading
*   **REQ-3.1 (Video Summaries):** The system shall accept audio/video file uploads, transcribe them using an AI API (e.g., Whisper), and generate bullet-point summaries via an LLM.
*   **REQ-3.2 (Homework Grading):** The system shall parse uploaded PDF assignments, send the text to an LLM with a grading rubric, and return a JSON containing error counts, feedback, and a suggested grade.

### 3.4 Offline Communication
*   **REQ-4.1 (Email Integration):** Students can click "Ask Question" offline, which will open their native email client (`mailto:`) pre-filled with the course and lecturer details.

## 4. Non-Functional Requirements
*   **Usability (KISS):** The student interface must be heavily optimized for mobile devices with large touch targets.
*   **Reliability:** The client app must implement lightweight polling to stay synchronized with the lecturer's screen state without crashing or disconnecting.
*   **Security:** API keys for OpenAI/Gemini must be stored securely on the backend and never exposed to the client.