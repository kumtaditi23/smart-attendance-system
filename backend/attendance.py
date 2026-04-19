import cv2
import os
import sys
import face_recognition
from datetime import datetime

sys.path.insert(0, os.path.dirname(__file__))

from recognition  import load_encodings, identify_faces
from database     import create_tables, mark_attendance, get_attendance_today
from face_detection import start_camera
from liveness     import LivenessChecker, draw_liveness_overlay, REQUIRED_BLINKS


def run_attendance_session():
    """
    Attendance session with liveness (blink) detection.

    Flow:
      1. Face detected + recognised → enter liveness check
      2. Student must blink REQUIRED_BLINKS times
      3. Only after blinks confirmed → mark attendance in DB
      4. Photo shown on phone = no blinks possible = rejected
    """
    create_tables()

    known_encodings, known_labels = load_encodings()
    if not known_encodings:
        print("[ERROR] No faces enrolled. Add photos to known_faces/ first.")
        return

    print(f"[ATTENDANCE] {len(known_encodings)} student(s) loaded.")
    print(f"[ATTENDANCE] Blink detection ON — {REQUIRED_BLINKS} blinks required.")
    print("[ATTENDANCE] Press Q to quit.\n")

    cap         = start_camera()
    frame_count = 0

    # track per-student liveness checker instances
    # key = student_id, value = LivenessChecker()
    liveness_checkers = {}

    # students fully verified this session
    marked_today = set()

    # pre-load already marked today
    already = {r["student_id"] for r in get_attendance_today()}
    marked_today.update(already)

    last_results = []

    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                break

            frame_count += 1

            if frame_count % 2 == 0:
                rgb            = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                face_locations = face_recognition.face_locations(rgb, model="hog")

                if face_locations:
                    last_results = identify_faces(
                        frame, face_locations,
                        known_encodings, known_labels
                    )
                else:
                    last_results = []
                    liveness_checkers.clear()   # reset if no face visible

            display = frame.copy()

            for r in last_results:
                sid  = r["student_id"]
                name = r["name"]
                loc  = r["location"]

                # Already marked — show green tick, skip liveness
                if sid and sid in marked_today:
                    top, right, bottom, left = loc
                    cv2.rectangle(display, (left, top), (right, bottom),
                                  (0, 200, 0), 2)
                    cv2.rectangle(display, (left, bottom - 32),
                                  (right, bottom), (0, 200, 0), cv2.FILLED)
                    cv2.putText(display, f"{name}  PRESENT",
                                (left + 5, bottom - 10),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.52,
                                (255, 255, 255), 1)
                    continue

                # Unknown face — show red box, no liveness
                if not sid:
                    top, right, bottom, left = loc
                    cv2.rectangle(display, (left, top), (right, bottom),
                                  (0, 0, 220), 2)
                    cv2.rectangle(display, (left, bottom - 32),
                                  (right, bottom), (0, 0, 220), cv2.FILLED)
                    cv2.putText(display, "Unknown",
                                (left + 5, bottom - 10),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.52,
                                (255, 255, 255), 1)
                    continue

                # Known but not yet marked — run liveness check
                if sid not in liveness_checkers:
                    liveness_checkers[sid] = LivenessChecker()
                    print(f"[LIVENESS] Starting check for {name} — "
                          f"please blink {REQUIRED_BLINKS} times")

                checker = liveness_checkers[sid]

                if not checker.passed and not checker.failed:
                    result = checker.update(display, loc)
                    display = draw_liveness_overlay(display, loc, result, name)

                elif checker.passed:
                    # Blinks confirmed — mark attendance once
                    success = mark_attendance(sid, name)
                    if success:
                        marked_today.add(sid)
                        print(f"[MARKED]   {name} ({sid}) — liveness passed "
                              f"— {datetime.now().strftime('%H:%M:%S')}")
                    liveness_checkers.pop(sid, None)

                elif checker.failed:
                    # Timed out — reset so they can try again
                    print(f"[LIVENESS] {name} timed out — resetting.")
                    liveness_checkers.pop(sid, None)

            # Status bar
            h, w = display.shape[:2]
            cv2.rectangle(display, (0, 0), (w, 36), (20, 20, 20), cv2.FILLED)
            ts = datetime.now().strftime("%Y-%m-%d  %H:%M:%S")
            cv2.putText(display, ts, (10, 24),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.52, (160, 160, 160), 1)
            cv2.putText(display, f"Present: {len(marked_today)}", (w - 140, 24),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.52, (100, 220, 100), 1)
            cv2.putText(display, "Blink detection ON", (w // 2 - 75, 24),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 200, 255), 1)

            cv2.imshow("Smart Attendance — Blink to verify", display)

            if cv2.waitKey(1) & 0xFF == ord('q'):
                break

    finally:
        cap.release()
        cv2.destroyAllWindows()
        print_summary(marked_today, known_labels)


def print_summary(marked_today, known_labels):
    label_map = {lbl.split("|")[0]: lbl.split("|")[1] for lbl in known_labels}
    print("\n" + "=" * 42)
    print(f"  SESSION SUMMARY — {datetime.now().strftime('%Y-%m-%d')}")
    print("=" * 42)
    if not marked_today:
        print("  No attendance marked.")
    else:
        for sid in sorted(marked_today):
            print(f"  PRESENT  {label_map.get(sid, sid):20s} ({sid})")
    print(f"\n  Total present : {len(marked_today)}")
    print("=" * 42 + "\n")


if __name__ == "__main__":
    print("=" * 50)
    print("  SMART ATTENDANCE — BLINK DETECTION ENABLED")
    print("=" * 50 + "\n")
    run_attendance_session()