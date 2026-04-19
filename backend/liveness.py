import cv2
import numpy as np
import face_recognition
from scipy.spatial import distance as dist

# ── Eye Aspect Ratio (EAR) ─────────────────────────────────────────────────────
# EAR drops sharply when eyes close — this is how we detect blinks.
# Formula: EAR = (|p2-p6| + |p3-p5|) / (2 * |p1-p4|)
# When eyes are open  → EAR ≈ 0.25–0.30
# When eyes are closed → EAR < 0.20

EAR_THRESHOLD   = 0.20   # below this = eyes closed
BLINK_FRAMES    = 2      # eyes must be closed for at least N frames
REQUIRED_BLINKS = 2      # number of blinks required to pass liveness


def get_eye_landmarks(face_encoding_shape, face_location, frame):
    """
    Use dlib's 68-point landmark model via face_recognition to get eye points.
    Returns (left_eye_points, right_eye_points) or (None, None) if not found.
    """
    top, right, bottom, left = face_location
    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

    landmarks_list = face_recognition.face_landmarks(
        rgb,
        face_locations=[face_location]
    )

    if not landmarks_list:
        return None, None

    landmarks     = landmarks_list[0]
    left_eye_pts  = landmarks.get("left_eye",  [])
    right_eye_pts = landmarks.get("right_eye", [])

    return left_eye_pts, right_eye_pts


def compute_ear(eye_points):
    """Compute Eye Aspect Ratio from 6 eye landmark points."""
    if len(eye_points) < 6:
        return 0.3   # default open value

    pts = np.array(eye_points, dtype=float)

    # Vertical distances
    A = dist.euclidean(pts[1], pts[5])
    B = dist.euclidean(pts[2], pts[4])
    # Horizontal distance
    C = dist.euclidean(pts[0], pts[3])

    ear = (A + B) / (2.0 * C) if C > 0 else 0.3
    return ear


def draw_eyes(frame, left_eye, right_eye, color=(0, 255, 0)):
    """Draw eye contours on frame for visual feedback."""
    if left_eye:
        pts = np.array(left_eye, dtype=np.int32)
        cv2.polylines(frame, [pts], True, color, 1)
    if right_eye:
        pts = np.array(right_eye, dtype=np.int32)
        cv2.polylines(frame, [pts], True, color, 1)
    return frame


# ── Liveness Checker Class ─────────────────────────────────────────────────────

class LivenessChecker:
    """
    Tracks blink state for a single face.
    Create one instance per student being verified.

    Usage:
        checker = LivenessChecker()
        while not checker.passed:
            result = checker.update(frame, face_location)
            # result has: blink_count, ear, eyes_closed, passed, message
    """

    def __init__(self):
        self.blink_count      = 0
        self.closed_frames    = 0
        self.eyes_were_closed = False
        self.passed           = False
        self.failed           = False
        self.frame_count      = 0
        self.MAX_FRAMES       = 300   # ~10 seconds at 30fps to complete

    def update(self, frame, face_location):
        """
        Process one frame. Returns a result dict.
        """
        self.frame_count += 1

        # Timeout — too slow = possible photo attack
        if self.frame_count > self.MAX_FRAMES and not self.passed:
            self.failed = True
            return {
                "blink_count":  self.blink_count,
                "ear":          0,
                "eyes_closed":  False,
                "passed":       False,
                "failed":       True,
                "message":      "Timeout — please try again"
            }

        left_eye, right_eye = get_eye_landmarks(None, face_location, frame)

        if left_eye is None or right_eye is None:
            return {
                "blink_count":  self.blink_count,
                "ear":          0.3,
                "eyes_closed":  False,
                "passed":       False,
                "failed":       False,
                "message":      f"Blink {REQUIRED_BLINKS - self.blink_count}x to verify"
            }

        left_ear  = compute_ear(left_eye)
        right_ear = compute_ear(right_eye)
        ear       = (left_ear + right_ear) / 2.0

        eyes_closed = ear < EAR_THRESHOLD

        if eyes_closed:
            self.closed_frames += 1
        else:
            # Eyes just opened after being closed long enough = one blink
            if self.closed_frames >= BLINK_FRAMES:
                self.blink_count += 1
                print(f"[LIVENESS] Blink detected! ({self.blink_count}/{REQUIRED_BLINKS})")
            self.closed_frames = 0

        if self.blink_count >= REQUIRED_BLINKS:
            self.passed = True

        remaining = max(0, REQUIRED_BLINKS - self.blink_count)
        if self.passed:
            message = "Liveness verified!"
        elif eyes_closed:
            message = "Eyes closing..."
        else:
            message = f"Please blink {remaining} more time(s)"

        return {
            "blink_count":  self.blink_count,
            "ear":          round(ear, 3),
            "eyes_closed":  eyes_closed,
            "passed":       self.passed,
            "failed":       self.failed,
            "message":      message
        }

    def reset(self):
        self.__init__()


# ── Draw liveness overlay ──────────────────────────────────────────────────────

def draw_liveness_overlay(frame, face_location, result, name=""):
    """
    Draw liveness status on frame:
    - Blink counter progress bar
    - Status message
    - Eye contour dots
    - Colour-coded border (yellow=checking, green=passed, red=failed)
    """
    top, right, bottom, left = face_location
    h, w = frame.shape[:2]

    # Border colour
    if result["passed"]:
        color = (0, 220, 0)      # green
    elif result["failed"]:
        color = (0, 0, 220)      # red
    else:
        color = (0, 200, 255)    # yellow — checking

    # Face box
    cv2.rectangle(frame, (left, top), (right, bottom), color, 2)

    # Progress bar above face box
    bar_w     = right - left
    progress  = min(result["blink_count"] / REQUIRED_BLINKS, 1.0)
    filled_w  = int(bar_w * progress)

    cv2.rectangle(frame, (left, top - 12), (right, top - 4),
                  (60, 60, 60), cv2.FILLED)
    if filled_w > 0:
        cv2.rectangle(frame, (left, top - 12),
                      (left + filled_w, top - 4), color, cv2.FILLED)

    # Status message below face box
    msg = result["message"]
    if name and result["passed"]:
        msg = f"{name} — Verified!"

    cv2.rectangle(frame, (left, bottom), (right, bottom + 28),
                  color, cv2.FILLED)
    cv2.putText(frame, msg, (left + 4, bottom + 19),
                cv2.FONT_HERSHEY_SIMPLEX, 0.48, (255, 255, 255), 1)

    # Instruction banner at bottom of frame
    if not result["passed"] and not result["failed"]:
        banner_y = h - 44
        cv2.rectangle(frame, (0, banner_y), (w, h),
                      (20, 20, 60), cv2.FILLED)
        blinks_left = REQUIRED_BLINKS - result["blink_count"]
        cv2.putText(frame,
                    f"Anti-spoof check: blink {blinks_left} more time(s) to mark attendance",
                    (10, h - 16),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.52, (100, 200, 255), 1)

    return frame


if __name__ == "__main__":
    print("[TEST] Liveness module loaded OK.")
    print(f"       EAR threshold : {EAR_THRESHOLD}")
    print(f"       Blinks required: {REQUIRED_BLINKS}")
    print("       Import this module into attendance.py and app.py")