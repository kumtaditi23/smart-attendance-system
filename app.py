import os, sys, threading, cv2, face_recognition
from flask import (Flask, render_template, Response, jsonify,
                   request, redirect, url_for, session, send_file)
from datetime import datetime
import csv, io

BASE_DIR    = os.path.dirname(__file__)
BACKEND_DIR = os.path.join(BASE_DIR, "backend")
sys.path.insert(0, BACKEND_DIR)

from backend.database    import (create_tables,
                          add_subject, get_all_subjects, get_subject_by_code, delete_subject,
                          add_student, get_all_students, delete_student,
                          mark_attendance, get_attendance_today, get_attendance_by_date,
                          get_subject_summary, get_student_subject_report,
                          get_total_classes_per_subject)
from backend.recognition import load_encodings, identify_faces
from backend.liveness    import LivenessChecker, draw_liveness_overlay, REQUIRED_BLINKS

app = Flask(__name__)
app.secret_key = "attendance_secret_2024"

# ── Global camera state ────────────────────────────────────────────────────────
camera_lock      = threading.Lock()
camera_active    = False
latest_frame     = None
session_marked   = set()
liveness_state   = {}
active_subject   = None   # subject_code currently selected

known_encodings  = []
known_labels     = []

ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "admin123"

def login_required(f):
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if "logged_in" not in session:
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated

# ── Auth ───────────────────────────────────────────────────────────────────────
@app.route("/")
def index():
    return redirect(url_for("login") if "logged_in" not in session else url_for("dashboard"))

@app.route("/login", methods=["GET","POST"])
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

# ── Pages ──────────────────────────────────────────────────────────────────────
@app.route("/dashboard")
@login_required
def dashboard():
    subjects       = get_all_subjects()
    today_records  = get_attendance_today()
    total_students = len(get_all_students())
    total_present  = len(set(r["student_id"] for r in today_records))
    classes_today  = len(set(r["subject_code"] for r in today_records))
    return render_template("dashboard.html",
                           subjects=subjects,
                           today_records=today_records,
                           total_students=total_students,
                           total_present=total_present,
                           classes_today=classes_today,
                           date=datetime.now().strftime("%B %d, %Y"))

@app.route("/attendance")
@login_required
def attendance_page():
    subjects = get_all_subjects()
    return render_template("attendance.html", subjects=subjects)

@app.route("/subjects")
@login_required
def subjects_page():
    subjects = get_all_subjects()
    totals   = {r["subject_code"]: r["total_classes"]
                for r in get_total_classes_per_subject()}
    return render_template("subjects.html", subjects=subjects, totals=totals)

@app.route("/admin")
@login_required
def admin():
    students = get_all_students()
    return render_template("admin.html", students=students)

@app.route("/reports")
@login_required
def reports():
    date         = request.args.get("date", datetime.now().strftime("%Y-%m-%d"))
    subject_code = request.args.get("subject", "")
    subjects     = get_all_subjects()
    records      = get_attendance_by_date(date, subject_code or None)
    summary      = get_subject_summary(subject_code or None)
    totals       = {r["subject_code"]: r["total_classes"]
                    for r in get_total_classes_per_subject()}
    return render_template("reports.html",
                           records=records,
                           subjects=subjects,
                           summary=summary,
                           totals=totals,
                           selected_date=date,
                           selected_subject=subject_code)

@app.route("/student/<student_id>")
@login_required
def student_detail(student_id):
    from backend.database import get_student_by_id
    student = get_student_by_id(student_id)
    report  = get_student_subject_report(student_id)
    totals  = {r["subject_code"]: r["total_classes"]
               for r in get_total_classes_per_subject()}
    return render_template("student_detail.html",
                           student=student,
                           report=report,
                           totals=totals)

# ── Camera thread ──────────────────────────────────────────────────────────────
def camera_thread():
    global latest_frame, camera_active, session_marked, liveness_state
    global known_encodings, known_labels, active_subject

    cap         = cv2.VideoCapture(0)
    frame_count = 0
    last_results = []

     # ── WARM UP FIX ── give camera 1 second to initialise
    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)  # reduce buffer lag
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
    cap.set(cv2.CAP_PROP_FPS, 30)        # request 30fps
    
    # Discard first 8 frames — camera needs to adjust exposure
    for _ in range(8):
        cap.read()


    subject = get_subject_by_code(active_subject) if active_subject else None
    subj_label = f"{subject['subject_name']} — {subject['teacher_name']}" if subject else "No subject"

    while camera_active:
        ret, frame = cap.read()
        if not ret:
            break

        frame_count += 1
        display = frame.copy()

        if frame_count % 2 == 0 and known_encodings:
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            face_locations = face_recognition.face_locations(rgb, model="hog")
            if face_locations:
                last_results = identify_faces(frame, face_locations,
                                              known_encodings, known_labels)
            else:
                last_results = []
                liveness_state.clear()

        for r in last_results:
            sid  = r["student_id"]
            name = r["name"]
            loc  = r["location"]

            if sid and sid in session_marked:
                top, right, bottom, left = loc
                cv2.rectangle(display, (left,top),(right,bottom),(0,200,0),2)
                cv2.rectangle(display, (left,bottom-32),(right,bottom),(0,200,0),cv2.FILLED)
                cv2.putText(display, f"{name}  PRESENT",
                            (left+5,bottom-10), cv2.FONT_HERSHEY_SIMPLEX,.52,(255,255,255),1)
                continue

            if not sid:
                top, right, bottom, left = loc
                cv2.rectangle(display,(left,top),(right,bottom),(0,0,220),2)
                cv2.rectangle(display,(left,bottom-32),(right,bottom),(0,0,220),cv2.FILLED)
                cv2.putText(display,"Unknown",(left+5,bottom-10),
                            cv2.FONT_HERSHEY_SIMPLEX,.52,(255,255,255),1)
                continue

            if sid not in liveness_state:
                liveness_state[sid] = LivenessChecker()

            checker = liveness_state[sid]
            if checker.failed:
                liveness_state[sid] = LivenessChecker()
                checker = liveness_state[sid]

            if not checker.passed:
                result  = checker.update(display, loc)
                display = draw_liveness_overlay(display, loc, result, name)
            else:
                if active_subject:
                    success = mark_attendance(sid, name, active_subject)
                    if success:
                        session_marked.add(sid)
                        print(f"[MARKED] {name} — {subj_label} — {datetime.now().strftime('%H:%M:%S')}")
                liveness_state.pop(sid, None)

        # Status bar
        h, w = display.shape[:2]
        cv2.rectangle(display,(0,0),(w,36),(20,20,20),cv2.FILLED)
        cv2.putText(display, datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    (10,24),cv2.FONT_HERSHEY_SIMPLEX,.48,(160,160,160),1)
        cv2.putText(display, subj_label[:40],
                    (w//2-120,24),cv2.FONT_HERSHEY_SIMPLEX,.45,(100,220,255),1)
        cv2.putText(display, f"Present: {len(session_marked)}",
                    (w-120,24),cv2.FONT_HERSHEY_SIMPLEX,.48,(100,220,100),1)

        _, buffer = cv2.imencode(".jpg", display, [cv2.IMWRITE_JPEG_QUALITY,60])
        with camera_lock:
            latest_frame = buffer.tobytes()

    cap.release()
    camera_active = False

def generate_frames():
    import time
    # Wait up to 3 seconds for first frame
    waited = 0
    while not latest_frame and waited < 3.0:
        time.sleep(0.1)
        waited += 0.1

    while camera_active:
        with camera_lock:
            frame = latest_frame
        if frame:
            yield (b"--frame\r\n"
                   b"Content-Type: image/jpeg\r\n\r\n" + frame + b"\r\n")
        import time; time.sleep(0.03)  # ~30fps cap

@app.route("/video_feed")
@login_required
def video_feed():
    return Response(generate_frames(),
                    mimetype="multipart/x-mixed-replace; boundary=frame")

# ── API ────────────────────────────────────────────────────────────────────────
@app.route("/api/camera/start", methods=["POST"])
@login_required
def start_camera():
    global camera_active, session_marked, liveness_state
    global known_encodings, known_labels, active_subject
    data = request.get_json()
    subject_code = data.get("subject_code", "")
    if not subject_code:
        return jsonify({"success": False, "error": "Please select a subject first."}), 400
    subject = get_subject_by_code(subject_code)
    if not subject:
        return jsonify({"success": False, "error": "Subject not found."}), 404
    if not camera_active:
        known_encodings, known_labels = load_encodings()
        session_marked  = set()
        liveness_state  = {}
        active_subject  = subject_code
        camera_active   = True
        t = threading.Thread(target=camera_thread, daemon=True)
        t.start()
        return jsonify({"status": "started",
                        "enrolled": len(known_encodings),
                        "subject": subject["subject_name"],
                        "teacher": subject["teacher_name"]})
    return jsonify({"status": "already_running"})

@app.route("/api/camera/stop", methods=["POST"])
@login_required
def stop_camera():
    global camera_active
    camera_active = False
    return jsonify({"status": "stopped", "marked": len(session_marked)})

@app.route("/api/attendance/today")
@login_required
def api_today():
    subject_code = request.args.get("subject", None)
    return jsonify([dict(r) for r in get_attendance_today(subject_code)])

@app.route("/api/subjects", methods=["GET"])
@login_required
def api_subjects():
    return jsonify([dict(s) for s in get_all_subjects()])

@app.route("/api/subjects/add", methods=["POST"])
@login_required
def api_add_subject():
    data         = request.get_json()
    code         = data.get("subject_code","").strip()
    name         = data.get("subject_name","").strip()
    teacher      = data.get("teacher_name","").strip()
    if not code or not name or not teacher:
        return jsonify({"success":False,"error":"All fields required."}),400
    success = add_subject(code, name, teacher)
    if success:
        return jsonify({"success":True,"message":f"{name} added."})
    return jsonify({"success":False,"error":"Subject code already exists."}),409

@app.route("/api/subjects/delete/<code>", methods=["DELETE"])
@login_required
def api_delete_subject(code):
    delete_subject(code)
    return jsonify({"success":True})

@app.route("/api/students/add", methods=["POST"])
@login_required
def api_add_student():
    data = request.get_json()
    name = data.get("name","").strip()
    sid  = data.get("student_id","").strip()
    if not name or not sid:
        return jsonify({"success":False,"error":"Name and ID required."}),400
    success = add_student(name, sid)
    if success:
        return jsonify({"success":True,"message":f"{name} added."})
    return jsonify({"success":False,"error":"Student ID already exists."}),409

@app.route("/api/students/delete/<student_id>", methods=["DELETE"])
@login_required
def api_delete_student(student_id):
    delete_student(student_id)
    return jsonify({"success":True})

@app.route("/api/export/csv")
@login_required
def export_csv():
    date    = request.args.get("date", datetime.now().strftime("%Y-%m-%d"))
    subject = request.args.get("subject","")
    records = get_attendance_by_date(date, subject or None)
    output  = io.StringIO()
    writer  = csv.writer(output)
    writer.writerow(["Name","Student ID","Subject","Teacher","Date","Time","Status"])
    for r in records:
        writer.writerow([r["name"],r["student_id"],r["subject_name"],
                         r["teacher_name"],r["date"],r["time"],r["status"]])
    output.seek(0)
    fname = f"attendance_{subject or 'all'}_{date}.csv"
    return send_file(io.BytesIO(output.getvalue().encode()),
                     mimetype="text/csv", as_attachment=True,
                     download_name=fname)

if __name__ == "__main__":
    print("="*50)
    print("  SMART ATTENDANCE — Subject-wise Mode")
    print("="*50)
    create_tables()
    print(f"[SETUP] Blink detection ON — {REQUIRED_BLINKS} blinks required")
    print("[SERVER] http://localhost:5000  |  admin / admin123\n")
    app.run(debug=True, host="0.0.0.0", port=5000, use_reloader=False)