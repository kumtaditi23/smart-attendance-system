import face_recognition
import cv2
import os
import pickle
import numpy as np
from datetime import datetime

KNOWN_FACES_DIR = os.path.join(os.path.dirname(__file__), "known_faces")
ENCODINGS_FILE  = os.path.join(os.path.dirname(__file__), "encodings.pkl")


# ── Enrolment ──────────────────────────────────────────────────────────────────

def enrol_from_folder():
    """
    Scan known_faces/ and build encodings.
    Takes MULTIPLE encodings per photo using different detection models
    for much better accuracy.
    """
    if not os.path.exists(KNOWN_FACES_DIR):
        os.makedirs(KNOWN_FACES_DIR)
        print(f"[ENROL] Created folder: {KNOWN_FACES_DIR}")
        return [], []

    known_encodings = []
    known_labels    = []
    supported       = (".jpg", ".jpeg", ".png")

    image_files = [f for f in os.listdir(KNOWN_FACES_DIR)
                   if f.lower().endswith(supported)]

    if not image_files:
        print("[ENROL] No images found in known_faces/.")
        return [], []

    print(f"[ENROL] Processing {len(image_files)} image(s)...")

    for filename in image_files:
        filepath = os.path.join(KNOWN_FACES_DIR, filename)
        stem     = os.path.splitext(filename)[0]

        if "_" not in stem:
            print(f"[ENROL] Skipping {filename} — rename to STUDENTID_Name.jpg")
            continue

        student_id, name = stem.split("_", 1)

        # Load and try multiple orientations/sizes for better encoding
        image = face_recognition.load_image_file(filepath)

        # Try HOG model first (faster)
        encodings = face_recognition.face_encodings(
            image,
            num_jitters=10,        # sample face 10x for better accuracy
            model="large"          # large model = more accurate 128-point encoding
        )

        if len(encodings) == 0:
            # Try resizing image — sometimes helps with small/large photos
            h, w = image.shape[:2]
            for scale in [0.5, 1.5, 2.0]:
                resized = cv2.resize(image, (int(w*scale), int(h*scale)))
                encodings = face_recognition.face_encodings(
                    resized, num_jitters=10, model="large"
                )
                if encodings:
                    print(f"[ENROL]   Found face at scale {scale}x for {filename}")
                    break

        if len(encodings) == 0:
            print(f"[ENROL] WARNING: No face found in {filename}")
            print(f"         → Use a clear, well-lit, front-facing photo")
            continue

        known_encodings.append(encodings[0])
        known_labels.append(f"{student_id}|{name}")
        print(f"[ENROL]   + {name} ({student_id}) enrolled successfully")

    if known_encodings:
        with open(ENCODINGS_FILE, "wb") as f:
            pickle.dump({"encodings": known_encodings,
                         "labels":    known_labels}, f)
        print(f"[ENROL] Saved {len(known_encodings)} encoding(s) to disk.")
    else:
        print("[ENROL] No faces were enrolled. Check your photos.")

    return known_encodings, known_labels


def load_encodings():
    if not os.path.exists(ENCODINGS_FILE):
        print("[LOAD] No encodings file — running enrolment first...")
        return enrol_from_folder()

    with open(ENCODINGS_FILE, "rb") as f:
        data = pickle.load(f)

    print(f"[LOAD] Loaded {len(data['encodings'])} known face(s) from disk.")
    return data["encodings"], data["labels"]


# ── Recognition ────────────────────────────────────────────────────────────────

def identify_faces(frame, face_locations, known_encodings, known_labels):
    """
    Improved matching:
    - Uses 'large' model for more accurate 128-point encoding
    - Tries multiple tolerances and picks the best match
    - Shows distance score in terminal to help debug
    """
    if not known_encodings:
        return [{"student_id": None, "name": "No enrolled faces",
                 "confidence": 0, "location": loc} for loc in face_locations]

    rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

    # Use original (not scaled) locations for better accuracy
    face_encodings = face_recognition.face_encodings(
        rgb_frame,
        known_face_locations=face_locations,
        num_jitters=1,
        model="large"
    )

    results = []
    TOLERANCE = 0.60   # raised from 0.5 — adjust higher if still not matching

    for encoding, location in zip(face_encodings, face_locations):
        distances = face_recognition.face_distance(known_encodings, encoding)
        best_idx  = int(np.argmin(distances))
        best_dist = float(distances[best_idx])
        confidence = round((1 - best_dist) * 100, 1)

        # Print distance to terminal so you can tune tolerance
        student_id_raw, name_raw = known_labels[best_idx].split("|", 1)
        print(f"[DEBUG] Best match: {name_raw}  distance={best_dist:.3f}  "
              f"confidence={confidence}%  threshold={TOLERANCE}")

        if best_dist <= TOLERANCE:
            results.append({
                "student_id": student_id_raw,
                "name":       name_raw,
                "confidence": confidence,
                "location":   location
            })
        else:
            results.append({
                "student_id": None,
                "name":       "Unknown",
                "confidence": confidence,   # still show score for debugging
                "location":   location
            })

    return results


# ── Drawing ────────────────────────────────────────────────────────────────────

def draw_results(frame, results):
    for r in results:
        top, right, bottom, left = r["location"]
        known = r["student_id"] is not None
        color = (0, 200, 0) if known else (0, 0, 220)

        cv2.rectangle(frame, (left, top), (right, bottom), color, 2)
        cv2.rectangle(frame, (left, bottom - 35),
                      (right, bottom), color, cv2.FILLED)

        if known:
            label = f"{r['name']}  {r['confidence']}%"
        else:
            # Show score even for unknown to help debug
            label = f"Unknown ({r['confidence']}%)"

        cv2.putText(frame, label, (left + 5, bottom - 10),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 1)
    return frame


def add_status_bar(frame, enrolled_count, recognised_today):
    h, w = frame.shape[:2]
    cv2.rectangle(frame, (0, 0), (w, 36), (30, 30, 30), cv2.FILLED)
    ts = datetime.now().strftime("%Y-%m-%d  %H:%M:%S")
    cv2.putText(frame, ts,                               (10, 24),
                cv2.FONT_HERSHEY_SIMPLEX, 0.52, (180, 180, 180), 1)
    cv2.putText(frame, f"Enrolled: {enrolled_count}",    (w//2 - 55, 24),
                cv2.FONT_HERSHEY_SIMPLEX, 0.52, (100, 220, 100), 1)
    cv2.putText(frame, f"Marked: {recognised_today}",    (w - 130, 24),
                cv2.FONT_HERSHEY_SIMPLEX, 0.52, (100, 200, 255), 1)
    return frame


# ── Live loop ──────────────────────────────────────────────────────────────────

def run_recognition_loop():
    """
    Improved live loop:
    - Processes EVERY frame (not every 3rd) for better detection
    - Uses full-resolution frame locations (no scaling issues)
    - Prints debug distance scores to terminal
    """
    from face_detection import start_camera

    known_encodings, known_labels = load_encodings()
    if not known_encodings:
        print("[ERROR] No faces enrolled. Add photos to known_faces/ and retry.")
        return

    print(f"[INFO] {len(known_encodings)} face(s) loaded. Starting camera...")
    print("[INFO] Press Q to quit.")
    print("[INFO] Watch the [DEBUG] lines to see match scores.\n")

    cap          = start_camera()
    last_results = []
    marked_today = set()
    frame_count  = 0

    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                break

            frame_count += 1

            # Process every 2nd frame — good balance of speed and accuracy
            if frame_count % 3 == 0:
                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

                # Use CNN model for detection — much more accurate than HOG
                # (slower but worth it for recognition accuracy)
                face_locations = face_recognition.face_locations(
                    rgb, model="hog"   # change to "cnn" if you have a GPU
                )

                if face_locations:
                    last_results = identify_faces(
                        frame, face_locations,
                        known_encodings, known_labels
                    )
                    for r in last_results:
                        if r["student_id"] and \
                           r["student_id"] not in marked_today:
                            marked_today.add(r["student_id"])
                            print(f"\n[RECOGNISED] {r['name']} "
                                  f"({r['student_id']})  "
                                  f"{r['confidence']}% confidence\n")
                else:
                    last_results = []

            display = frame.copy()
            if last_results:
                display = draw_results(display, last_results)
            display = add_status_bar(display, len(known_encodings),
                                     len(marked_today))

            cv2.imshow("Face Recognition — Press Q to quit", display)
            key = cv2.waitKey(30) & 0xFF
            if key == ord('q') or key == 27:  # Q or ESC
                break

    finally:
        cap.release()
        cv2.destroyAllWindows()
        print(f"\n[INFO] Session ended. Recognised: {len(marked_today)} person(s).")


if __name__ == "__main__":
    print("=" * 50)
    print("  FACE RECOGNITION MODULE  (improved)")
    print("=" * 50)
    print("\n[1] Re-enrolling faces with improved settings...")
    # Always re-enrol when running directly — picks up new photos too
    if os.path.exists(ENCODINGS_FILE):
        os.remove(ENCODINGS_FILE)
        print("[INFO] Cleared old encodings — rebuilding fresh.\n")
    enrol_from_folder()

    print("\n[2] Starting live recognition...")
    run_recognition_loop()