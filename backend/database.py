import sqlite3
import os
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(__file__), "attendance.db")


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def create_tables():
    conn = get_connection()
    cursor = conn.cursor()

    # Students
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS students (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            name        TEXT    NOT NULL,
            student_id  TEXT    UNIQUE NOT NULL,
            enrolled_at TEXT    NOT NULL
        )
    """)

    # Subjects — with teacher name
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS subjects (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            subject_code  TEXT    UNIQUE NOT NULL,
            subject_name  TEXT    NOT NULL,
            teacher_name  TEXT    NOT NULL,
            created_at    TEXT    NOT NULL
        )
    """)

    # Attendance — now linked to a subject
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS attendance (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id    TEXT    NOT NULL,
            name          TEXT    NOT NULL,
            subject_code  TEXT    NOT NULL,
            subject_name  TEXT    NOT NULL,
            teacher_name  TEXT    NOT NULL,
            date          TEXT    NOT NULL,
            time          TEXT    NOT NULL,
            status        TEXT    NOT NULL DEFAULT 'Present',
            FOREIGN KEY (student_id)   REFERENCES students(student_id),
            FOREIGN KEY (subject_code) REFERENCES subjects(subject_code)
        )
    """)

    conn.commit()
    conn.close()
    print("[DB] Tables created (or already exist).")


# ── Subject functions ──────────────────────────────────────────────────────────

def add_subject(subject_code, subject_name, teacher_name):
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO subjects (subject_code, subject_name, teacher_name, created_at)
            VALUES (?, ?, ?, ?)
        """, (subject_code.upper(), subject_name, teacher_name,
              datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        conn.commit()
        conn.close()
        print(f"[DB] Subject added: {subject_name} ({subject_code}) — {teacher_name}")
        return True
    except sqlite3.IntegrityError:
        print(f"[DB] Subject code '{subject_code}' already exists.")
        return False


def get_all_subjects():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM subjects ORDER BY subject_name")
    subjects = cursor.fetchall()
    conn.close()
    return subjects


def get_subject_by_code(subject_code):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM subjects WHERE subject_code = ?",
                   (subject_code.upper(),))
    subject = cursor.fetchone()
    conn.close()
    return subject


def delete_subject(subject_code):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM attendance WHERE subject_code = ?", (subject_code,))
    cursor.execute("DELETE FROM subjects WHERE subject_code = ?", (subject_code,))
    conn.commit()
    conn.close()
    print(f"[DB] Subject {subject_code} deleted.")


# ── Student functions ──────────────────────────────────────────────────────────

def add_student(name, student_id):
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO students (name, student_id, enrolled_at)
            VALUES (?, ?, ?)
        """, (name, student_id, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        conn.commit()
        conn.close()
        print(f"[DB] Student added: {name} ({student_id})")
        return True
    except sqlite3.IntegrityError:
        print(f"[DB] Student ID '{student_id}' already exists.")
        return False


def get_all_students():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM students ORDER BY name")
    students = cursor.fetchall()
    conn.close()
    return students


def get_student_by_id(student_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM students WHERE student_id = ?", (student_id,))
    student = cursor.fetchone()
    conn.close()
    return student


def delete_student(student_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM attendance WHERE student_id = ?", (student_id,))
    cursor.execute("DELETE FROM students WHERE student_id = ?", (student_id,))
    conn.commit()
    conn.close()
    print(f"[DB] Student {student_id} deleted.")


# ── Attendance functions ───────────────────────────────────────────────────────

def mark_attendance(student_id, name, subject_code):
    """
    Mark attendance for a student in a specific subject.
    One mark per student per subject per day.
    """
    subject = get_subject_by_code(subject_code)
    if not subject:
        print(f"[DB] Subject '{subject_code}' not found.")
        return False

    today    = datetime.now().strftime("%Y-%m-%d")
    now_time = datetime.now().strftime("%H:%M:%S")

    conn = get_connection()
    cursor = conn.cursor()

    # Check duplicate: same student + same subject + same day
    cursor.execute("""
        SELECT id FROM attendance
        WHERE student_id = ? AND subject_code = ? AND date = ?
    """, (student_id, subject_code, today))

    if cursor.fetchone():
        conn.close()
        print(f"[DB] {name} already marked for {subject['subject_name']} today.")
        return False

    cursor.execute("""
        INSERT INTO attendance
        (student_id, name, subject_code, subject_name, teacher_name, date, time, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, 'Present')
    """, (student_id, name, subject_code,
          subject["subject_name"], subject["teacher_name"],
          today, now_time))

    conn.commit()
    conn.close()
    print(f"[DB] {name} marked for {subject['subject_name']} at {now_time}")
    return True


def get_attendance_today(subject_code=None):
    conn = get_connection()
    cursor = conn.cursor()
    today = datetime.now().strftime("%Y-%m-%d")
    if subject_code:
        cursor.execute("""
            SELECT * FROM attendance
            WHERE date = ? AND subject_code = ?
            ORDER BY time DESC
        """, (today, subject_code))
    else:
        cursor.execute("""
            SELECT * FROM attendance WHERE date = ?
            ORDER BY subject_name, time DESC
        """, (today,))
    records = cursor.fetchall()
    conn.close()
    return records


def get_attendance_by_date(date, subject_code=None):
    conn = get_connection()
    cursor = conn.cursor()
    if subject_code:
        cursor.execute("""
            SELECT * FROM attendance
            WHERE date = ? AND subject_code = ?
            ORDER BY time DESC
        """, (date, subject_code))
    else:
        cursor.execute("""
            SELECT * FROM attendance WHERE date = ?
            ORDER BY subject_name, time DESC
        """, (date,))
    records = cursor.fetchall()
    conn.close()
    return records


def get_attendance_by_subject(subject_code):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT * FROM attendance
        WHERE subject_code = ?
        ORDER BY date DESC, time DESC
    """, (subject_code,))
    records = cursor.fetchall()
    conn.close()
    return records


def get_attendance_by_student(student_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT * FROM attendance
        WHERE student_id = ?
        ORDER BY date DESC, subject_name
    """, (student_id,))
    records = cursor.fetchall()
    conn.close()
    return records


def get_subject_summary(subject_code=None):
    """
    Returns per-student attendance count.
    If subject_code given → for that subject only.
    """
    conn = get_connection()
    cursor = conn.cursor()
    if subject_code:
        cursor.execute("""
            SELECT s.name, s.student_id,
                   COUNT(a.id) AS classes_attended
            FROM students s
            LEFT JOIN attendance a
              ON s.student_id = a.student_id
             AND a.subject_code = ?
            GROUP BY s.student_id
            ORDER BY s.name
        """, (subject_code,))
    else:
        cursor.execute("""
            SELECT s.name, s.student_id,
                   COUNT(a.id) AS classes_attended
            FROM students s
            LEFT JOIN attendance a ON s.student_id = a.student_id
            GROUP BY s.student_id
            ORDER BY s.name
        """)
    summary = cursor.fetchall()
    conn.close()
    return summary


def get_student_subject_report(student_id):
    """
    Per-student breakdown: how many classes attended per subject.
    """
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT
            sub.subject_code,
            sub.subject_name,
            sub.teacher_name,
            COUNT(a.id) AS classes_attended
        FROM subjects sub
        LEFT JOIN attendance a
          ON sub.subject_code = a.subject_code
         AND a.student_id = ?
        GROUP BY sub.subject_code
        ORDER BY sub.subject_name
    """, (student_id,))
    report = cursor.fetchall()
    conn.close()
    return report


def get_total_classes_per_subject():
    """Total number of unique class days held per subject."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT subject_code, subject_name, teacher_name,
               COUNT(DISTINCT date) AS total_classes
        FROM attendance
        GROUP BY subject_code
    """)
    data = cursor.fetchall()
    conn.close()
    return data


if __name__ == "__main__":
    print("[TEST] Setting up subject-wise database...")
    create_tables()

    add_subject("CS101", "Python Programming", "Dr. Sharma")
    add_subject("CS102", "Java OOP",           "Prof. Mehta")
    add_subject("CS103", "Data Structures",    "Dr. Patel")

    add_student("Aditi",   "STU001")
    add_student("Anjana",  "STU002")
    add_student("Rajveer", "STU023")

    mark_attendance("STU001", "Aditi",   "CS101")
    mark_attendance("STU002", "Anjana",  "CS101")
    mark_attendance("STU001", "Aditi",   "CS102")
    mark_attendance("STU001", "Aditi",   "CS101")  # duplicate — blocked

    print("\n[TEST] Today CS101:")
    for r in get_attendance_today("CS101"):
        print(f"  {r['name']} — {r['subject_name']} — {r['teacher_name']} — {r['time']}")

    print("\n[TEST] Aditi subject report:")
    for r in get_student_subject_report("STU001"):
        print(f"  {r['subject_name']:20s} ({r['teacher_name']}) — {r['classes_attended']} class(es)")

    print("\n[TEST] database.py subject-wise working!")