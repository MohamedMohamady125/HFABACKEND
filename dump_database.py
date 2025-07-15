import mysql.connector

# Set your DB credentials
DB_CONFIG = {
    "host": "localhost",
    "user": "root",
    "password": "MmmM12345!",
    "database": "hfa"
}

# List of tables you want to export
TABLES = [
    "users", "athletes", "registration_requests", "attendance", "payments",
    "branches", "threads", "posts", "notifications", "massage_bookings", "practice_sessions",
    "performance_logs", "health_logs", "coach_assignments", "device_tokens"
    # Add others as needed
]

def dump_database(output_file="db_dump.txt"):
    conn = mysql.connector.connect(**DB_CONFIG)
    cursor = conn.cursor(dictionary=True)

    with open(output_file, "w", encoding="utf-8") as f:
        for table in TABLES:
            f.write(f"\n\n=== {table.upper()} ===\n")
            try:
                cursor.execute(f"SELECT * FROM {table}")
                rows = cursor.fetchall()
                if rows:
                    for row in rows:
                        f.write(str(row) + "\n")
                else:
                    f.write("No data found.\n")
            except Exception as e:
                f.write(f"⚠️ Error fetching table '{table}': {e}\n")

    cursor.close()
    conn.close()
    print(f"✅ Database dumped to {output_file}")

if __name__ == "__main__":
    dump_database()