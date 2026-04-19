# Smart Attendance System 🎓

A real-time face recognition attendance system with **blink-based liveness detection** to prevent spoofing. Built with Python, Flask, OpenCV, and SQLite.

## Features

- **Live face recognition** via webcam — identifies enrolled students instantly
- **Blink detection** — rejects phone photos, only real faces are accepted
- **Auto attendance marking** — marks present once per student per day
- **Web dashboard** — view today's attendance, stats, and charts
- **Admin panel** — add and remove students
- **Reports** — filter by date, export to CSV
- **Login system** — password-protected admin access
- **Git collaboration** — built by two students using GitHub

## Tech Stack

| Layer | Technology |
|---|---|
| Backend / AI | Python 3.10, face_recognition, OpenCV |
| Web Framework | Flask |
| Database | SQLite |
| Frontend | HTML, CSS, JavaScript, Chart.js |
| Anti-spoof | Blink detection (Eye Aspect Ratio) |

## Project Structure

```
attendance_system/
├── app.py                  ← Flask server — run this to start
├── README.md
├── .gitignore
├── backend/
│   ├── face_detection.py   ← webcam + face detection
│   ├── recognition.py      ← face enrolment + matching
│   ├── attendance.py       ← standalone attendance session
│   ├── liveness.py         ← blink detection (anti-spoof)
│   ├── database.py         ← SQLite operations
│   └── known_faces/        ← student photos go here
└── templates/
    ├── base.html
    ├── login.html
    ├── dashboard.html
    ├── attendance.html
    ├── admin.html
    └── reports.html
```

## Installation

### 1. Clone the repository
```bash
git clone https://github.com/kumtaditi23/smart-attendance-system.git
cd smart-attendance-system
```

### 2. Install dependencies
```bash
pip install flask face_recognition opencv-python scipy
```

> **Windows users:** If `face_recognition` fails to install, first install:
> ```bash
> pip install cmake dlib
> pip install face_recognition
> ```

### 3. Add student photos
Add photos to `backend/known_faces/` using this naming format:
```
STU001_Student Name.jpg
STU002_Another Name.jpg
```
- Use a clear, front-facing, well-lit photo
- One face per photo
- Supported formats: `.jpg`, `.jpeg`, `.png`

### 4. Enrol faces
```bash
cd backend
python recognition.py
```
You should see each student enrolled successfully.

### 5. Run the app
```bash
cd ..
python app.py
```

### 6. Open in browser
```
http://localhost:5000
```
Login with: **admin** / **admin123**

## How to Use

1. Go to **Take Attendance** page
2. Click **Start Camera**
3. Students stand in front of the webcam one by one
4. System detects face → asks student to **blink twice** (liveness check)
5. After blinking → automatically marked **Present** in the database
6. View results on **Dashboard**
7. Export records from **Reports** page

## Anti-Spoofing

This system uses **Eye Aspect Ratio (EAR)** blink detection. When a face is recognised, the student must blink 2 times before attendance is marked. A photo on a phone screen cannot blink, so it will be rejected automatically.

## Team

| Role | Responsibilities |
|---|---|
| Student 1 (AI + Backend) | Face detection, recognition, liveness, database, Flask API |
| Student 2 (Frontend) | Login UI, dashboard, admin panel, reports, charts |

## Built With

- [face_recognition](https://github.com/ageitgey/face_recognition) — face detection and encoding
- [OpenCV](https://opencv.org/) — webcam and image processing
- [Flask](https://flask.palletsprojects.com/) — web framework
- [Chart.js](https://www.chartjs.org/) — dashboard charts
- [SQLite](https://www.sqlite.org/) — local database