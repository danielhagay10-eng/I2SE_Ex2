# 📋 Statement of Work (SoW)

## 1. Project Background
Current classroom teaching tools are heavily siloed, overly complex, and fail to leverage modern AI capabilities to enhance real-time learning. This project delivers an end-to-end, web-based teaching tool optimized for in-class use, built on the KISS principle.

## 2. Project Objectives
*   To design a lightweight web application for both lecturers (desktop view) and students (smartphone view).
*   To automate attendance tracking using dynamic QR codes and AI vision validation.
*   To facilitate real-time, low-friction interactions (questions and volunteering) without disrupting the lecture flow.
*   To integrate LLM capabilities for automated lecture summaries and deep homework reviews.

## 3. Scope of Work (In-Scope)
*   **Design & Architecture:** Definition of use cases, SRS, software components, and UML diagrams.
*   **Demo Implementation:** A functional prototype built with Python (FastAPI), SQLite, and HTML/JS.
*   **Core Features Delivery:** 
    *   QR-based attendance with AI headcount verification.
    *   Real-time "Red/Green" interaction buttons.
    *   Video summary generation pipeline.
    *   Homework analysis pipeline.
*   **Live Demonstration:** A robust 10-minute live demo in class.

## 4. Out of Scope
*   Integration with external university systems (מידע אישי).
*   Integration with Zoom or Moodle APIs.
*   Complex user authentication (OAuth) for the demo (mock logins will be used to save time).
*   Production-level deployment scaling.

## 5. Deliverables & Milestones
1.  **Phase 1:** Requirements & Architecture Documentation (README, SoW, SRS, UML).
2.  **Phase 2:** Technical Prototype (Backend API & Frontend UI).
3.  **Phase 3:** AI Integration (Vision headcount, transcription, homework analysis).
4.  **Phase 4:** Testing & Demo Preparation.