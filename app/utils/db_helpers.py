# Use this file to avoid circular import from db.py
from app.database import get_connection

def get_user_by_email(email: str):
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT id, email FROM users WHERE email = %s", (email,))
    return cursor.fetchone()