import mysql.connector

# Replace with your actual database credentials
DB_CONFIG = {
    "host": "localhost",
    "user": "root",
    "password": "MmmM12345!",
    "database": "hfa"
}

def get_database_schema():
    conn = mysql.connector.connect(**DB_CONFIG)
    cursor = conn.cursor()

    print("=== DATABASE SCHEMA ===\n")

    cursor.execute("SHOW TABLES")
    tables = cursor.fetchall()

    for (table_name,) in tables:
        print(f"\n=== {table_name.upper()} ===")
        cursor.execute(f"DESCRIBE {table_name}")
        columns = cursor.fetchall()

        for column in columns:
            field, col_type, nullable, key, default, extra = column
            print(f"{field:<20} {col_type:<20} {nullable:<8} {key:<5} {default if default is not None else 'NULL'} {extra}")

    cursor.close()
    conn.close()

if __name__ == "__main__":
    get_database_schema()