"""
Create a lightweight starter bundle (2 multi-table Spider-schema demo SQLite DBs)
so the frontend & backend can be tested locally immediately before running
`prepare_spider_bundle.py` with the full Spider dataset.

Usage:
    python scripts/create_demo_data.py
"""

from __future__ import annotations

import json
import shutil
import sqlite3
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
THESIS_ROOT = BACKEND_DIR.parents[1]
OUT_DIR = BACKEND_DIR / "data"


def _create_concert_singer(db_path: Path) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    if db_path.exists():
        db_path.unlink()
    conn = sqlite3.connect(db_path)
    conn.executescript(
        """
        CREATE TABLE stadium (
            Stadium_ID INTEGER PRIMARY KEY,
            Location TEXT,
            Name TEXT,
            Capacity INTEGER,
            Highest INTEGER,
            Lowest INTEGER,
            Average INTEGER
        );
        CREATE TABLE singer (
            Singer_ID INTEGER PRIMARY KEY,
            Name TEXT,
            Country TEXT,
            Song_Name TEXT,
            Song_release_year TEXT,
            Age INTEGER,
            Is_male BOOLEAN
        );
        CREATE TABLE concert (
            concert_ID INTEGER PRIMARY KEY,
            concert_Name TEXT,
            Theme TEXT,
            Stadium_ID INTEGER,
            Year TEXT,
            FOREIGN KEY (Stadium_ID) REFERENCES stadium(Stadium_ID)
        );
        CREATE TABLE singer_in_concert (
            concert_ID INTEGER,
            Singer_ID INTEGER,
            PRIMARY KEY (concert_ID, Singer_ID),
            FOREIGN KEY (concert_ID) REFERENCES concert(concert_ID),
            FOREIGN KEY (Singer_ID) REFERENCES singer(Singer_ID)
        );

        INSERT INTO stadium VALUES
            (1, 'Raith Rovers', 'Stark''s Park', 10104, 4812, 1294, 2106),
            (2, 'Ayr United', 'Somerset Park', 11998, 2363, 1057, 1477),
            (3, 'East Fife', 'Bayview Stadium', 2000, 1980, 533, 864),
            (4, 'Queen''s Park', 'Hampden Park', 52500, 1763, 466, 730);

        INSERT INTO singer VALUES
            (1, 'Joe Sharp', 'Netherlands', 'You', '1992', 52, 1),
            (2, 'Timbaland', 'United States', 'Dangerous', '2008', 32, 1),
            (3, 'Justin Brown', 'France', 'Hey Oh', '2013', 29, 1),
            (4, 'Rose White', 'France', 'Sun', '2003', 41, 0),
            (5, 'John Nizinik', 'France', 'Gentleman', '2014', 43, 1),
            (6, 'Tribal King', 'France', 'Love', '2016', 25, 1);

        INSERT INTO concert VALUES
            (1, 'Auditions', 'Free choice', 1, '2014'),
            (2, 'Super bootcamp', 'Free choice 2', 2, '2014'),
            (3, 'Home Visits', 'Bleeding Love', 2, '2015'),
            (4, 'Week 1', 'Wide Awake', 4, '2014'),
            (5, 'Week 2', 'Party All Night', 3, '2015');

        INSERT INTO singer_in_concert VALUES
            (1, 2), (1, 3), (1, 5),
            (2, 3), (2, 6),
            (3, 5),
            (4, 4), (4, 1),
            (5, 2), (5, 3);
        """
    )
    conn.commit()
    conn.close()


def _create_student_transcripts(db_path: Path) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    if db_path.exists():
        db_path.unlink()
    conn = sqlite3.connect(db_path)
    conn.executescript(
        """
        CREATE TABLE Departments (
            department_id INTEGER PRIMARY KEY,
            department_name TEXT,
            department_description TEXT
        );
        CREATE TABLE Degree_Programs (
            degree_program_id INTEGER PRIMARY KEY,
            department_id INTEGER,
            degree_summary_name TEXT,
            degree_summary_description TEXT,
            FOREIGN KEY (department_id) REFERENCES Departments(department_id)
        );
        CREATE TABLE Courses (
            course_id INTEGER PRIMARY KEY,
            course_name TEXT,
            course_description TEXT
        );
        CREATE TABLE Sections (
            section_id INTEGER PRIMARY KEY,
            course_id INTEGER,
            section_name TEXT,
            section_description TEXT,
            FOREIGN KEY (course_id) REFERENCES Courses(course_id)
        );
        CREATE TABLE Semesters (
            semester_id INTEGER PRIMARY KEY,
            semester_name TEXT,
            semester_description TEXT
        );
        CREATE TABLE Students (
            student_id INTEGER PRIMARY KEY,
            first_name TEXT,
            last_name TEXT,
            email_address TEXT,
            date_first_registered TEXT
        );
        CREATE TABLE Student_Enrolment (
            student_enrolment_id INTEGER PRIMARY KEY,
            degree_program_id INTEGER,
            semester_id INTEGER,
            student_id INTEGER,
            FOREIGN KEY (degree_program_id) REFERENCES Degree_Programs(degree_program_id),
            FOREIGN KEY (semester_id) REFERENCES Semesters(semester_id),
            FOREIGN KEY (student_id) REFERENCES Students(student_id)
        );
        CREATE TABLE Student_Enrolment_Courses (
            student_course_id INTEGER PRIMARY KEY,
            course_id INTEGER,
            student_enrolment_id INTEGER,
            FOREIGN KEY (course_id) REFERENCES Courses(course_id),
            FOREIGN KEY (student_enrolment_id) REFERENCES Student_Enrolment(student_enrolment_id)
        );
        CREATE TABLE Transcripts (
            transcript_id INTEGER PRIMARY KEY,
            transcript_date TEXT,
            other_details TEXT
        );
        CREATE TABLE Transcript_Contents (
            student_course_id INTEGER,
            transcript_id INTEGER,
            PRIMARY KEY (student_course_id, transcript_id),
            FOREIGN KEY (student_course_id) REFERENCES Student_Enrolment_Courses(student_course_id),
            FOREIGN KEY (transcript_id) REFERENCES Transcripts(transcript_id)
        );

        INSERT INTO Departments VALUES
            (1, 'Computer Science', 'Software, AI, and systems'),
            (2, 'Mathematics', 'Pure and applied mathematics'),
            (3, 'Statistics', 'Data science and statistical inference');

        INSERT INTO Degree_Programs VALUES
            (1, 1, 'Bachelor', 'B.Sc. in Computer Science'),
            (2, 1, 'Master', 'M.Sc. in Artificial Intelligence'),
            (3, 2, 'Bachelor', 'B.Sc. in Applied Mathematics'),
            (4, 3, 'Master', 'M.Sc. in Data Science');

        INSERT INTO Courses VALUES
            (1, 'Database Systems', 'Relational algebra and SQL'),
            (2, 'Machine Learning', 'Supervised and unsupervised learning'),
            (3, 'Algorithms', 'Graph algorithms and complexity'),
            (4, 'Probability Theory', 'Distributions and stochastic processes');

        INSERT INTO Sections VALUES
            (1, 1, 'CS-301A', 'Fall morning section'),
            (2, 2, 'CS-410A', 'Fall afternoon section'),
            (3, 3, 'CS-205A', 'Spring core section'),
            (4, 4, 'STAT-300A', 'Spring seminar');

        INSERT INTO Semesters VALUES
            (1, 'Fall 2025', 'Autumn semester'),
            (2, 'Spring 2026', 'Spring semester');

        INSERT INTO Students VALUES
            (1, 'Alice', 'Tan', 'alice@uni.edu', '2023-09-01'),
            (2, 'Budi', 'Santoso', 'budi@uni.edu', '2024-09-01'),
            (3, 'Clara', 'Wijaya', 'clara@uni.edu', '2023-09-01'),
            (4, 'Daniel', 'Pratama', 'daniel@uni.edu', '2025-01-15');

        INSERT INTO Student_Enrolment VALUES
            (1, 1, 1, 1),
            (2, 2, 1, 2),
            (3, 1, 2, 1),
            (4, 4, 2, 3),
            (5, 3, 2, 4);

        INSERT INTO Student_Enrolment_Courses VALUES
            (1, 1, 1), (2, 3, 1),
            (3, 2, 2),
            (4, 2, 3),
            (5, 1, 4), (6, 4, 4),
            (7, 4, 5);

        INSERT INTO Transcripts VALUES
            (1, '2026-01-20', 'Official Fall 2025'),
            (2, '2026-06-15', 'Official Spring 2026');

        INSERT INTO Transcript_Contents VALUES
            (1, 1), (2, 1), (3, 1),
            (4, 2), (5, 2), (6, 2), (7, 2);
        """
    )
    conn.commit()
    conn.close()


DEMO_TABLES = [
    {
        "db_id": "student_transcripts_tracking",
        "table_names_original": [
            "Departments", "Degree_Programs", "Courses", "Sections", "Semesters",
            "Students", "Student_Enrolment", "Student_Enrolment_Courses",
            "Transcripts", "Transcript_Contents",
        ],
        "table_names": [
            "departments", "degree programs", "courses", "sections", "semesters",
            "students", "student enrolment", "student enrolment courses",
            "transcripts", "transcript contents",
        ],
        "column_names_original": [
            [-1, "*"],
            [0, "department_id"], [0, "department_name"], [0, "department_description"],
            [1, "degree_program_id"], [1, "department_id"], [1, "degree_summary_name"], [1, "degree_summary_description"],
            [2, "course_id"], [2, "course_name"], [2, "course_description"],
            [3, "section_id"], [3, "course_id"], [3, "section_name"], [3, "section_description"],
            [4, "semester_id"], [4, "semester_name"], [4, "semester_description"],
            [5, "student_id"], [5, "first_name"], [5, "last_name"], [5, "email_address"], [5, "date_first_registered"],
            [6, "student_enrolment_id"], [6, "degree_program_id"], [6, "semester_id"], [6, "student_id"],
            [7, "student_course_id"], [7, "course_id"], [7, "student_enrolment_id"],
            [8, "transcript_id"], [8, "transcript_date"], [8, "other_details"],
            [9, "student_course_id"], [9, "transcript_id"],
        ],
        "column_names": [
            [-1, "*"],
            [0, "department id"], [0, "department name"], [0, "department description"],
            [1, "degree program id"], [1, "department id"], [1, "degree summary name"], [1, "degree summary description"],
            [2, "course id"], [2, "course name"], [2, "course description"],
            [3, "section id"], [3, "course id"], [3, "section name"], [3, "section description"],
            [4, "semester id"], [4, "semester name"], [4, "semester description"],
            [5, "student id"], [5, "first name"], [5, "last name"], [5, "email address"], [5, "date first registered"],
            [6, "student enrolment id"], [6, "degree program id"], [6, "semester id"], [6, "student id"],
            [7, "student course id"], [7, "course id"], [7, "student enrolment id"],
            [8, "transcript id"], [8, "transcript date"], [8, "other details"],
            [9, "student course id"], [9, "transcript id"],
        ],
        "column_types": [
            "text",
            "number", "text", "text",
            "number", "number", "text", "text",
            "number", "text", "text",
            "number", "number", "text", "text",
            "number", "text", "text",
            "number", "text", "text", "text", "time",
            "number", "number", "number", "number",
            "number", "number", "number",
            "number", "time", "text",
            "number", "number",
        ],
        "primary_keys": [1, 4, 8, 11, 15, 18, 23, 27, 30, 33],
        "foreign_keys": [
            [5, 1], [12, 8], [24, 4], [25, 15], [26, 18], [28, 8], [29, 23], [33, 27], [34, 30],
        ],
    },
    {
        "db_id": "concert_singer",
        "table_names_original": ["stadium", "singer", "concert", "singer_in_concert"],
        "table_names": ["stadium", "singer", "concert", "singer in concert"],
        "column_names_original": [
            [-1, "*"],
            [0, "Stadium_ID"], [0, "Location"], [0, "Name"], [0, "Capacity"], [0, "Highest"], [0, "Lowest"], [0, "Average"],
            [1, "Singer_ID"], [1, "Name"], [1, "Country"], [1, "Song_Name"], [1, "Song_release_year"], [1, "Age"], [1, "Is_male"],
            [2, "concert_ID"], [2, "concert_Name"], [2, "Theme"], [2, "Stadium_ID"], [2, "Year"],
            [3, "concert_ID"], [3, "Singer_ID"],
        ],
        "column_names": [
            [-1, "*"],
            [0, "stadium id"], [0, "location"], [0, "name"], [0, "capacity"], [0, "highest"], [0, "lowest"], [0, "average"],
            [1, "singer id"], [1, "name"], [1, "country"], [1, "song name"], [1, "song release year"], [1, "age"], [1, "is male"],
            [2, "concert id"], [2, "concert name"], [2, "theme"], [2, "stadium id"], [2, "year"],
            [3, "concert id"], [3, "singer id"],
        ],
        "column_types": [
            "text",
            "number", "text", "text", "number", "number", "number", "number",
            "number", "text", "text", "text", "text", "number", "others",
            "number", "text", "text", "number", "text",
            "number", "number",
        ],
        "primary_keys": [1, 8, 15, 20],
        "foreign_keys": [[18, 1], [20, 15], [21, 8]],
    },
]

DEMO_CATALOG = {
    "databases": [
        {
            "db_id": "student_transcripts_tracking",
            "display_name": "Student Transcripts & Courses (Demo)",
            "description": "University departments, degree programs, courses, sections, semesters, student enrollments, and transcripts.",
            "sample_questions": [
                {"question": "How many departments are there?", "difficulty": "Easy"},
                {"question": "List all course names and their descriptions.", "difficulty": "Easy"},
                {"question": "Which department offers the most degree programs?", "difficulty": "Medium"},
                {"question": "Show the first and last names of students enrolled in Fall 2025.", "difficulty": "Medium"},
                {"question": "Which courses are taken by Alice Tan?", "difficulty": "Hard"},
                {"question": "How many courses appear in each transcript?", "difficulty": "Hard"},
            ],
        },
        {
            "db_id": "concert_singer",
            "display_name": "Concerts & Singers (Demo)",
            "description": "Stadiums, singers, concert events, and performer lineups (Spider schema).",
            "sample_questions": [
                {"question": "How many singers do we have?", "difficulty": "Easy"},
                {"question": "Show name, country, and age for all singers ordered by age from oldest to youngest.", "difficulty": "Easy"},
                {"question": "What is the average, minimum, and maximum age of all singers from France?", "difficulty": "Easy"},
                {"question": "Show the stadium name and the number of concerts in each stadium.", "difficulty": "Medium"},
                {"question": "Show the concert name and theme along with the number of singers in each concert.", "difficulty": "Medium"},
                {"question": "What are the names of stadiums that have never held a concert?", "difficulty": "Hard"},
            ],
        },
    ]
}


def main() -> None:
    _create_student_transcripts(
        OUT_DIR / "databases" / "student_transcripts_tracking" / "student_transcripts_tracking.sqlite"
    )
    _create_concert_singer(OUT_DIR / "databases" / "concert_singer" / "concert_singer.sqlite")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "tables.json").write_text(json.dumps(DEMO_TABLES, indent=2), encoding="utf-8")
    (OUT_DIR / "catalog.json").write_text(json.dumps(DEMO_CATALOG, indent=2), encoding="utf-8")

    src_train = THESIS_ROOT / "data" / "skeletons" / "train.json"
    dst_train = OUT_DIR / "skeletons" / "train.json"
    if src_train.exists():
        dst_train.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src_train, dst_train)
        print(f"Copied train skeletons -> {dst_train}")

    print(f"Demo bundle created in {OUT_DIR}")


if __name__ == "__main__":
    main()
