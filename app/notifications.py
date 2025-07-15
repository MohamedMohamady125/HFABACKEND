from fastapi import APIRouter, Depends, HTTPException
from app.database import get_connection
from app.deps import get_current_user

router = APIRouter()

@router.get("/")
def get_notifications(user=Depends(get_current_user)):
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM notifications WHERE user_id = %s ORDER BY created_at DESC", (user["id"],))
    return cursor.fetchall()

@router.post("/")
def send_notification(user_id: int, message: str, user=Depends(get_current_user)):
    if user["role"] not in ["coach", "head_coach"]:
        raise HTTPException(status_code=403, detail="Only coaches can send notifications")

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO notifications (user_id, message) VALUES (%s, %s)", (user_id, message))
    conn.commit()
    return {"message": "Notification sent"}

@router.post("/read/{notification_id}")
def mark_as_read(notification_id: int, user=Depends(get_current_user)):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE notifications SET read_status = TRUE WHERE id = %s AND user_id = %s",
        (notification_id, user["id"])
    )
    conn.commit()
    return {"message": "Notification marked as read"}