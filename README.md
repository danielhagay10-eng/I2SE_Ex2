# 🎓 Vibe Coding & Deep Designing: Web-based Teaching Tool (Ex2)

Welcome to the **Web-based Teaching Tool** project repository! 🚀
This project is an end-to-end web application designed to simplify and improve the classroom learning experience, adhering to the principles of **KISS (Keep It Simple, Stupid)** and **Vibe Coding** (prioritizing the composition of existing tools over building from scratch).

---

## 🎯 Problem Statement
The current online tools for teaching are often too complex, lack real-time engagement, and do not adequately leverage modern AI (LLM) capabilities for proper learning. We need better, simpler, and AI-ready tools that work seamlessly during live lectures without the overhead of heavy integrations.

## 🔭 Project Scope
This project focuses on designing and demonstrating a standalone web application tailored for an in-class environment. 
**Key constraints & guidelines:**
* **Standalone System:** No integration with Moodle, Zoom, or university personal information systems (מידע אישי).
* **KISS Principle:** The primary interface for students must be a simple, accessible smartphone web app.
* **Demonstrability:** The system is designed strictly around what can be implemented and showcased in a 10-minute live class demo.
* **Vibe Coding Approach:** Emphasis is placed on using existing tools, open-source libraries, and APIs (Firebase, OpenAI/Gemini APIs, qrcode.js) rather than writing complex custom logic from scratch.

---

## ✨ Core Features

1. **📱 Automatic Attendance (The Main Feature)**
   * The lecturer generates a dynamic QR code on the main screen.
   * Students scan the QR code via the smartphone web app.
   * Attendance is instantly recorded and exported to a spreadsheet.
   * *Smart Validation:* The lecturer takes a quick photo of the class; AI (GPT/Gemini Vision) counts the students to verify attendance matches the scans (within a 5% margin).

2. **🔴 / 🟢 Real-Time Interaction & Polls (KISS)**
   * **Red Button (Question):** Students can send a text question to the lecturer instantly. The lecturer receives a floating notification on their screen.
   * **Green Button (Volunteer):** The lecturer asks a verbal question; students click to volunteer. The lecturer sees a live list and selects one to answer.
   * *Engagement Tracking:* Participation (questions/answers) is logged and categorized (0, 1-2, 3+ interactions) for end-of-class statistics.

3. **🎥 AI-Powered Video Summaries**
   * Lecturers can upload class audio/video recordings.
   * The system uses an ML transcription API (e.g., Whisper) and an LLM to automatically generate and display structured bullet-point summaries for the students.

4. **📝 Deep Homework Review & Comparison (LLM)**
   * Students submit assignments (e.g., PDFs).
   * An integrated LLM analyzes the submission, counts errors, provides deep feedback, and compares the work against the class average.
   * Grades and feedback are sent directly to the student via email.

---

## 📂 Repository Structure & Documentation
This repository contains the full design and planning documentation for the project:

* 📄 **README.md** - Project overview, problem statement, and scope (You are here!).
* 📄 **Tech_Report** - Technical-related tools report, detailing the APIs and libraries tested for the project.
* 📄 **SoW** - Statement of Work document.
* 📄 **SRS** - Software Requirements Specification document.
* 📄 **Architecture** - Main use cases, software components, and UML diagrams (Class & Sequence).
* 📄 **Testing_Strategy** - Testing strategy focusing on system classes and integration points.

---

## 🛠️ Technology Stack (Demo Implementation)
* **Frontend:** HTML/CSS/JavaScript (Optimized for Mobile/Tablet/Desktop).
* **Backend:** Python with **FastAPI**.
* **Database:** **SQLite** (Local) / Firebase (for real-time features).
* **AI Integrations:** Gemini API / OpenAI API (for Vision headcount, Video Summaries, and Homework grading).
* **Utilities:** `qrcode.js` (QR generation), `html5-qrcode` (Scanning).

---

> **Note on Implementation:** This repository is structured as a *Design Challenge*. The primary goal is the architecture and the rapid composition (Vibe Coding) of a functional 10-minute demo, proving the viability of these concepts in a live classroom setting.
