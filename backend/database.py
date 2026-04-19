import sqlite3
import os
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(__file__), "attendance.db")


def get_connection():
    """Return a connection to the SQLite database."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row  # lets you access columns by name
    return conn


def create_tables():
    """
    Create all tables if they don't already exist.
    Call this once when the app starts.
    """
    conn = get_connection()
    cursor = conn.cursor()

    # Table 1: students — stores enrolled people
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS students (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            name        TEXT    NOT NULL,
            student_id  TEXT    UNIQUE NOT NULL,
            enrolled_at TEXT    NOT NULL
        )
    """)

    # Table 2: attendance — one row per attendance event
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS attendance (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id  TEXT    NOT NULL,
            name        TEXT    NOT NULL,
            date        TEXT    NOT NULL,
            time        TEXT    NOT NULL,
            status      TEXT    NOT NULL DEFAULT 'Present',
            FOREIGN KEY (student_id) REFERENCES students(student_id)
        )
    """)

    conn.commit()
    conn.close()
    print("[DB] Tables created (or already exist).")


# ── Student functions ──────────────────────────────────────────────────────────

def add_student(name, student_id):
    """
    Add a new student to the database.
    Returns True if added, False if student_id already exists.
    """
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
    """Return a list of all enrolled students."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM students ORDER BY name")
    students = cursor.fetchall()
    conn.close()
    return students


def get_student_by_id(student_id):
    """Return a single student by their student_id, or None."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM students WHERE student_id = ?", (student_id,))
    student = cursor.fetchone()
    conn.close()
    return student


def delete_student(student_id):
    """Remove a student and all their attendance records."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM attendance WHERE student_id = ?", (student_id,))
    cursor.execute("DELETE FROM students WHERE student_id = ?", (student_id,))
    conn.commit()
    conn.close()
    print(f"[DB] Student {student_id} deleted.")


# ── Attendance functions ───────────────────────────────────────────────────────

def mark_attendance(student_id, name):
    """
    Mark a student as present for today.
    Prevents duplicate entries — one mark per student per day.
    Returns True if marked, False if already marked today.
    """
    today = datetime.now().strftime("%Y-%m-%d")
    now_time = datetime.now().strftime("%H:%M:%S")

    conn = get_connection()
    cursor = conn.cursor()

    # Check if already marked today
    cursor.execute("""
        SELECT id FROM attendance
        WHERE student_id = ? AND date = ?
    """, (student_id, today))

    if cursor.fetchone():
        conn.close()
        print(f"[DB] {name} already marked present today.")
        return False

    # Insert new attendance record
    cursor.execute("""
        INSERT INTO attendance (student_id, name, date, time, status)
        VALUES (?, ?, ?, ?, 'Present')
    """, (student_id, name, today, now_time))

    conn.commit()
    conn.close()
    print(f"[DB] Attendance marked: {name} at {now_time}")
    return True


def get_attendance_today():
    """Return all attendance records for today."""
    today = datetime.now().strftime("%Y-%m-%d")
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT * FROM attendance
        WHERE date = ?
        ORDER BY time DESC
    """, (today,))
    records = cursor.fetchall()
    conn.close()
    return records


def get_attendance_by_date(date):
    """Return attendance records for a specific date (format: YYYY-MM-DD)."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT * FROM attendance
        WHERE date = ?
        ORDER BY time DESC
    """, (date,))
    records = cursor.fetchall()
    conn.close()
    return records


def get_attendance_by_student(student_id):
    """Return all attendance records for a specific student."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT * FROM attendance
        WHERE student_id = ?
        ORDER BY date DESC, time DESC
    """, (student_id,))
    records = cursor.fetchall()
    conn.close()
    return records


def get_attendance_summary():
    """
    Return a summary: each student with total days present.
    Useful for the dashboard charts.
    """
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT s.name, s.student_id,
               COUNT(a.id) AS days_present
        FROM students s
        LEFT JOIN attendance a ON s.student_id = a.student_id
        GROUP BY s.student_id
        ORDER BY s.name
    """)
    summary = cursor.fetchall()
    conn.close()
    return summary


# ── Quick test ─────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("[TEST] Setting up database...")
    create_tables()

    # Add test students
    add_student("ADITI", "STU001")
    add_student("ANJANA", "STU002")
    add_student("ARCHISHA", "STU003")
    add_student("DIVYA", "STU004")
    add_student("DAKSH", "STU005")

    # Mark some attendance
    mark_attendance("STU001", "ADITI")
    mark_attendance("STU002", "ANJANA")
    mark_attendance("STU003", "ARCHISHA")
    mark_attendance("STU004", "DIVYA")
    mark_attendance("STU003", "DAKSH")
    mark_attendance("STU003", "RAJVEER")  # duplicate — should be blocked

    # Print today's attendance
    print("\n[TEST] Today's attendance:")
    for row in get_attendance_today():
        print(f"  {row['name']} — {row['time']}")

    # Print summary
    print("\n[TEST] Summary:")
    for row in get_attendance_summary():
        print(f"  {row['name']} — {row['days_present']} day(s) present")

    print("\n[TEST] database.py working correctly!")

    if __name__ == "__main__":
     print("[TEST] Setting up database...")
    create_tables()