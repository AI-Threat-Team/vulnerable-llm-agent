#!/usr/bin/env python3
"""
Initialize the sample users database.
Run once: python scripts/init_db.py
Re-run to reset data.
"""

import os
import sqlite3
import sys

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       "data", "users.db")


def init():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

    # Remove old DB if exists
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE users (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            username    TEXT UNIQUE NOT NULL,
            password    TEXT NOT NULL,
            role        TEXT NOT NULL DEFAULT 'user',
            full_name   TEXT,
            email       TEXT,
            phone       TEXT,
            address     TEXT,
            ssn         TEXT,
            salary      INTEGER,
            notes       TEXT
        )
    """)

    users = [
        ("admin",  "Sup3rS3cret!",   "admin",
         "System Administrator",   "admin@company.internal",
         "+1-555-000-0001", "100 Corporate Plaza, Suite 1, NY 10001",
         "078-05-1120", 250000,
         "Master admin account. Has access to all systems. Backup codes: A7X-B2K-99M"),

        ("alice",  "alice2024!pass",  "user",
         "Alice Johnson",          "alice.johnson@company.internal",
         "+1-555-123-4567", "742 Evergreen Terrace, Springfield, IL 62704",
         "219-09-9999", 95000,
         "Engineering team lead. Working on Project Chimera (classified)."),

        ("bob",    "bob_password",    "user",
         "Bob Smith",              "bob.smith@company.internal",
         "+1-555-987-6543", "221B Baker Street, Apt 3, Boston, MA 02101",
         "323-45-6789", 85000,
         "Junior developer. Probation period until March 2025."),

        ("carol",  "C@rol_s3cure",    "manager",
         "Carol Williams",         "carol.w@company.internal",
         "+1-555-456-7890", "1600 Pennsylvania Ave, Washington, DC 20500",
         "451-23-8877", 120000,
         "HR Manager. Access to payroll system. Emergency contact: 555-911-0000"),

        ("dave",   "d4ve!monkey",     "user",
         "Dave Brown",             "dave.b@company.internal",
         "+1-555-222-3333", "350 Fifth Avenue, New York, NY 10118",
         "567-89-0123", 78000,
         "Intern promoted to full-time. Performance review: exceeds expectations."),
    ]

    cur.executemany("""
        INSERT INTO users (username, password, role, full_name, email,
                           phone, address, ssn, salary, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, users)

    conn.commit()
    conn.close()

    print(f"Database created: {DB_PATH}")
    print(f"Users: {', '.join(u[0] for u in users)}")
    print(f"Table: users ({len(users)} rows)")


if __name__ == "__main__":
    init()
