import cv2
import face_recognition
import numpy as np
from datetime import datetime
from threading import Thread
cap = cv2.VideoCapture(0)


def start_camera(camera_index=0):
    """Open webcam and return the capture object."""
    cap = cv2.VideoCapture(camera_index)
    if not cap.isOpened():
        raise RuntimeError("Could not open webcam. Check if camera is connected.")
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 320)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 240)
    return cap


def detect_faces_in_frame(frame):
    """
    Detect face locations in a single frame.
    Returns list of (top, right, bottom, left) tuples.
    """
    process_this_frame = True

while True:
    success, frame = cap.read()
    if not success:
        break

    if process_this_frame:
        small_frame = cv2.resize(frame, (0, 0), fx=0.25, fy=0.25)
        rgb_small = small_frame[:, :, ::-1]

        # 🔥 IMPORTANT: use HOG (fast)
        face_locations = face_recognition.face_locations(rgb_small, model="hog")
        face_encodings = face_recognition.face_encodings(rgb_small, face_locations)

        # 👇 yaha tumhara existing matching code rahega

    process_this_frame = not process_this_frame


def get_face_encodings(frame, face_locations):
    """
    Get face encodings (128-dimension fingerprint) for detected faces.
    Returns list of encodings matching the face_locations list.
    """
    rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

    # Scale down locations for encoding (must match detection scale)
    small_locations = [
        (top // 4, right // 4, bottom // 4, left // 4)
        for (top, right, bottom, left) in face_locations
    ]

    encodings = face_recognition.face_encodings(rgb_frame, small_locations)
    return encodings


def draw_face_boxes(frame, face_locations, labels=None):
    """
    Draw bounding boxes and labels on the frame.
    labels: list of strings matching face_locations (e.g. names or 'Unknown')
    """
    for i, (top, right, bottom, left) in enumerate(face_locations):
        label = labels[i] if labels and i < len(labels) else "Detecting..."

        # Choose colour: green for known, red for unknown
        color = (0, 200, 0) if label != "Unknown" else (0, 0, 220)

        # Draw rectangle around face
        cv2.rectangle(frame, (left, top), (right, bottom), color, 2)

        # Draw label background bar
        cv2.rectangle(frame, (left, bottom - 30), (right, bottom), color, cv2.FILLED)

        # Draw label text
        cv2.putText(
            frame,
            label,
            (left + 6, bottom - 8),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            (255, 255, 255),
            1
        )

    return frame


def add_status_overlay(frame, status_text, face_count):
    """Add a status bar at the top of the frame."""
    h, w = frame.shape[:2]

    # Dark top bar
    cv2.rectangle(frame, (0, 0), (w, 36), (30, 30, 30), cv2.FILLED)

    # Timestamp left
    timestamp = datetime.now().strftime("%Y-%m-%d  %H:%M:%S")
    cv2.putText(frame, timestamp, (10, 24),
                cv2.FONT_HERSHEY_SIMPLEX, 0.55, (200, 200, 200), 1)

    # Status centre
    cv2.putText(frame, status_text, (w // 2 - 80, 24),
                cv2.FONT_HERSHEY_SIMPLEX, 0.55, (100, 220, 100), 1)

    # Face count right
    count_text = f"Faces: {face_count}"
    cv2.putText(frame, count_text, (w - 100, 24),
                cv2.FONT_HERSHEY_SIMPLEX, 0.55, (200, 200, 200), 1)

    return frame


def run_detection_loop():
    """
    Main loop: opens webcam, detects faces in real time.
    Press Q to quit.
    This version only detects — no recognition yet.
    Recognition is added in recognition.py.
    """
    print("[INFO] Starting face detection...")
    print("[INFO] Press Q to quit the window.")

    cap = start_camera()

    # Process every other frame to reduce CPU load
    frame_count = 0

    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                print("[ERROR] Failed to read frame from camera.")
                break

            frame_count += 1

            # Only detect on even frames (skip every other frame)
            if frame_count % 3 != 0:
                face_locations = detect_faces_in_frame(frame)
                encodings = get_face_encodings(frame, face_locations)

                # Labels are just "Detected" until recognition module is added
                labels = ["Detected"] * len(face_locations)

                frame = draw_face_boxes(frame, face_locations, labels)
                status = "Detection active"
            else:
                face_locations = []
                status = "Detection active"

            face_count = len(face_locations)
            frame = add_status_overlay(frame, status, face_count)

            cv2.imshow("Face Detection — Press Q to quit", frame)

            if cv2.waitKey(1) & 0xFF == ord('q'):
                print("[INFO] Quit signal received.")
                break

    finally:
        cap.release()
        cv2.destroyAllWindows()
        print("[INFO] Camera released. Detection stopped.")

class VideoCamera:
    def __init__(self):
        self.cap = cv2.VideoCapture(0)
        self.cap.set(3, 640)
        self.cap.set(4, 480)
        self.frame = None
        self.running = True

        Thread(target=self.update, daemon=True).start()

    def update(self):
        while self.running:
            success, frame = self.cap.read()
            if success:
                self.frame = frame

    def get_frame(self):
        return self.frame

    def stop(self):
        self.running = False
        self.cap.release()

# Run directly to test this module standalone
if __name__ == "__main__":
    run_detection_loop()