import os
import sys
import threading
import cv2
import face_recognition

from flask import (Flask, render_template, Response,
                   jsonify, request, redirect, url_for,
                   session, send_file)
from datetime import datetime
import csv
import io

# ── Path setup ─────────────────────────────────────────────────────────────────
BASE_DIR     = os.path.dirname(__file__)
BACKEND_DIR  = os.path.join(BASE_DIR, "backend")
sys.path.insert(0, BACKEND_DIR)

from database    import (create_tables, add_student, get_all_students,
                          delete_student, mark_attendance,
                          get_attendance_today, get_attendance_by_date,
                          get_attendance_by_student, get_attendance_summary)
from recognition import load_encodings, identify_faces

# ── Flask setup ────────────────────────────────────────────────────────────────
app = Flask(__name__)
app.secret_key = "attendance_secret_key_2024"

# ── Global camera state ────────────────────────────────────────────────────────
camera_lock     = threading.Lock()
camera_active   = False
latest_frame    = None
session_marked  = set()   # student_ids marked this session

known_encodings = []
known_labels    = []


# ══════════════════════════════════════════════════════════════════════════════
#  AUTH
# ══════════════════════════════════════════════════════════════════════════════

ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "admin123"


@app.route("/")
def index():
    if "logged_in" not in session:
        return redirect(url_for("login"))
    return redirect(url_for("dashboard"))


@app.route("/login", methods=["GET", "POST"])
def login():
    error = None
    if request.method == "POST":
        if (request.form.get("username") == ADMIN_USERNAME and
                request.form.get("password") == ADMIN_PASSWORD):
            session["logged_in"] = True
            return redirect(url_for("dashboard"))
        error = "Invalid username or password."
    return render_template("login.html", error=error)


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


def login_required(f):
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if "logged_in" not in session:
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated


# ══════════════════════════════════════════════════════════════════════════════
#  PAGES
# ══════════════════════════════════════════════════════════════════════════════

@app.route("/dashboard")
@login_required
def dashboard():
    today_records = get_attendance_today()
    summary       = get_attendance_summary()
    total_students = len(get_all_students())
    total_present  = len(today_records)
    return render_template("dashboard.html",
                           today_records=today_records,
                           summary=summary,
                           total_students=total_students,
                           total_present=total_present,
                           date=datetime.now().strftime("%B %d, %Y"))


@app.route("/attendance")
@login_required
def attendance_page():
    return render_template("attendance.html")


@app.route("/admin")
@login_required
def admin():
    students = get_all_students()
    return render_template("admin.html", students=students)


@app.route("/reports")
@login_required
def reports():
    date      = request.args.get("date", datetime.now().strftime("%Y-%m-%d"))
    records   = get_attendance_by_date(date)
    summary   = get_attendance_summary()
    return render_template("reports.html",
                           records=records,
                           summary=summary,
                           selected_date=date)


# ══════════════════════════════════════════════════════════════════════════════
#  CAMERA + FACE RECOGNITION STREAM
# ══════════════════════════════════════════════════════════════════════════════

def camera_thread():
    """
    Background thread: opens webcam, runs face recognition,
    marks attendance, stores latest JPEG frame for streaming.
    """
    global latest_frame, camera_active, session_marked
    global known_encodings, known_labels

    cap         = cv2.VideoCapture(0)
    frame_count = 0

    cap.set(cv2.CAP_PROP_FRAME_WIDTH,  640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

    last_results = []

    while camera_active:
        ret, frame = cap.read()
        if not ret:
            break

        frame_count += 1

        if frame_count % 2 == 0 and known_encodings:
            rgb            = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            face_locations = face_recognition.face_locations(rgb, model="hog")

            if face_locations:
                last_results = identify_faces(
                    frame, face_locations,
                    known_encodings, known_labels
                )
                for r in last_results:
                    sid = r["student_id"]
                    if sid and sid not in session_marked:
                        success = mark_attendance(sid, r["name"])
                        if success:
                            session_marked.add(sid)
                            print(f"[MARKED] {r['name']} at "
                                  f"{datetime.now().strftime('%H:%M:%S')}")
            else:
                last_results = []

        # Draw boxes on frame
        display = draw_web_results(frame.copy(), last_results, session_marked)

        # Add top bar
        h, w = display.shape[:2]
        cv2.rectangle(display, (0, 0), (w, 36), (30, 30, 30), cv2.FILLED)
        cv2.putText(display,
                    datetime.now().strftime("%Y-%m-%d  %H:%M:%S"),
                    (10, 24), cv2.FONT_HERSHEY_SIMPLEX,
                    0.52, (180, 180, 180), 1)
        cv2.putText(display,
                    f"Present: {len(session_marked)}",
                    (w - 130, 24), cv2.FONT_HERSHEY_SIMPLEX,
                    0.52, (100, 220, 100), 1)

        # Encode frame to JPEG
        _, buffer = cv2.imencode(".jpg", display,
                                 [cv2.IMWRITE_JPEG_QUALITY, 80])
        with camera_lock:
            latest_frame = buffer.tobytes()

    cap.release()
    camera_active = False
    print("[CAMERA] Thread stopped.")


def draw_web_results(frame, results, marked_set):
    for r in results:
        top, right, bottom, left = r["location"]
        sid   = r["student_id"]
        known = sid is not None

        if known and sid in marked_set:
            color, label = (0, 200, 0),   f"{r['name']}  PRESENT"
        elif known:
            color, label = (0, 165, 255), f"{r['name']}  {r['confidence']}%"
        else:
            color, label = (0, 0, 220),   "Unknown"

        cv2.rectangle(frame, (left, top), (right, bottom), color, 2)
        cv2.rectangle(frame, (left, bottom - 32),
                      (right, bottom), color, cv2.FILLED)
        cv2.putText(frame, label, (left + 5, bottom - 9),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.52, (255, 255, 255), 1)
    return frame


def generate_frames():
    """Yield MJPEG frames for the browser video stream."""
    while camera_active:
        with camera_lock:
            frame = latest_frame
        if frame:
            yield (b"--frame\r\n"
                   b"Content-Type: image/jpeg\r\n\r\n" + frame + b"\r\n")
        else:
            import time; time.sleep(0.05)


@app.route("/video_feed")
@login_required
def video_feed():
    return Response(generate_frames(),
                    mimetype="multipart/x-mixed-replace; boundary=frame")


# ══════════════════════════════════════════════════════════════════════════════
#  API ENDPOINTS  (called by frontend JavaScript)
# ══════════════════════════════════════════════════════════════════════════════

@app.route("/api/camera/start", methods=["POST"])
@login_required
def start_camera():
    global camera_active, session_marked, known_encodings, known_labels
    if not camera_active:
        known_encodings, known_labels = load_encodings()
        session_marked  = set()
        camera_active   = True
        t = threading.Thread(target=camera_thread, daemon=True)
        t.start()
        return jsonify({"status": "started",
                        "enrolled": len(known_encodings)})
    return jsonify({"status": "already_running"})


@app.route("/api/camera/stop", methods=["POST"])
@login_required
def stop_camera():
    global camera_active
    camera_active = False
    return jsonify({"status": "stopped",
                    "marked": len(session_marked)})


@app.route("/api/attendance/today")
@login_required
def api_today():
    records = get_attendance_today()
    return jsonify([dict(r) for r in records])


@app.route("/api/attendance/summary")
@login_required
def api_summary():
    summary = get_attendance_summary()
    return jsonify([dict(r) for r in summary])


@app.route("/api/students", methods=["GET"])
@login_required
def api_students():
    students = get_all_students()
    return jsonify([dict(s) for s in students])


@app.route("/api/students/add", methods=["POST"])
@login_required
def api_add_student():
    data = request.get_json()
    name       = data.get("name", "").strip()
    student_id = data.get("student_id", "").strip()
    if not name or not student_id:
        return jsonify({"success": False,
                        "error": "Name and student ID are required."}), 400
    success = add_student(name, student_id)
    if success:
        return jsonify({"success": True,
                        "message": f"{name} added successfully."})
    return jsonify({"success": False,
                    "error": "Student ID already exists."}), 409


@app.route("/api/students/delete/<student_id>", methods=["DELETE"])
@login_required
def api_delete_student(student_id):
    delete_student(student_id)
    return jsonify({"success": True})


@app.route("/api/attendance/date")
@login_required
def api_by_date():
    date    = request.args.get("date", datetime.now().strftime("%Y-%m-%d"))
    records = get_attendance_by_date(date)
    return jsonify([dict(r) for r in records])


@app.route("/api/export/csv")
@login_required
def export_csv():
    date    = request.args.get("date", datetime.now().strftime("%Y-%m-%d"))
    records = get_attendance_by_date(date)

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Name", "Student ID", "Date", "Time", "Status"])
    for row in records:
        writer.writerow([row["name"], row["student_id"],
                         row["date"], row["time"], row["status"]])

    output.seek(0)
    return send_file(
        io.BytesIO(output.getvalue().encode()),
        mimetype="text/csv",
        as_attachment=True,
        download_name=f"attendance_{date}.csv"
    )


@app.route("/api/session/status")
@login_required
def session_status():
    return jsonify({
        "camera_active": camera_active,
        "marked_count":  len(session_marked),
        "marked_ids":    list(session_marked)
    })


# ══════════════════════════════════════════════════════════════════════════════
#  STARTUP
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("=" * 50)
    print("  SMART ATTENDANCE SYSTEM — Flask Server")
    print("=" * 50)
    print("\n[SETUP] Initialising database...")
    create_tables()
    print("[SETUP] Database ready.")
    print("\n[SERVER] Starting at http://localhost:5000")
    print("[SERVER] Login: admin / admin123")
    print("[SERVER] Press CTRL+C to stop.\n")
    app.run(debug=True, host="0.0.0.0", port=5000, use_reloader=False)
    