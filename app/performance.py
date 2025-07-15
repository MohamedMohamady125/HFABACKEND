from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import List
from app.database import get_connection
from app.deps import get_current_user

router = APIRouter()

class PerformanceLogInput(BaseModel):
    event_name: str
    result_time: str

class ReplaceAllLogsInput(BaseModel):
    logs: List[PerformanceLogInput]

@router.post("/performance-logs/replace-all")  # ✅ FIXED: No /athlete prefix here
def replace_all_performance_logs(data: ReplaceAllLogsInput, user=Depends(get_current_user)):
    """
    Delete ALL existing performance logs for this athlete and create new ones.
    This ensures no duplicates and clean data.
    """
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        # Get athlete ID from user
        cursor.execute("SELECT id FROM athletes WHERE user_id = %s", (user["id"],))
        athlete = cursor.fetchone()
        if not athlete:
            raise HTTPException(status_code=404, detail="Athlete not found")

        athlete_id = athlete["id"]

        # STEP 1: Delete ALL existing logs for this athlete
        cursor.execute("""
            DELETE FROM performance_logs 
            WHERE athlete_id = %s
        """, (athlete_id,))
        
        deleted_count = cursor.rowcount
        print(f"🗑️ Deleted {deleted_count} existing logs for athlete {athlete_id}")

        # STEP 2: Insert all new logs
        created_count = 0
        from datetime import datetime
        current_date = datetime.now().strftime("%Y-%m-%d")  # Dynamic date
        
        for log in data.logs:
            if log.event_name.strip() and log.result_time.strip():  # Only save non-empty logs
                cursor.execute("""
                    INSERT INTO performance_logs (athlete_id, meet_name, meet_date, event_name, result_time)
                    VALUES (%s, %s, %s, %s, %s)
                """, (
                    athlete_id, 
                    "Training Session",  # Default meet name
                    current_date,        # Today's date
                    log.event_name.strip(), 
                    log.result_time.strip()
                ))
                created_count += 1

        conn.commit()
        
        print(f"✅ Created {created_count} new performance logs for athlete {athlete_id}")
        
        return {
            "success": True, 
            "message": f"Replaced all logs: deleted {deleted_count}, created {created_count}",
            "deleted_count": deleted_count,
            "created_count": created_count
        }

    except Exception as e:
        conn.rollback()  # Rollback in case of error
        print("❌ DB Replace Error:", e)
        raise HTTPException(status_code=500, detail="Failed to replace performance logs")
    finally:
        cursor.close()
        conn.close()

def safe_time_conversion(time_str):
    """Safely handles time string, returns as-is."""
    if not time_str:
        return ""
    return str(time_str).strip()

@router.get("/performance-logs")  # ✅ FIXED: No /athlete prefix here
def get_athlete_performance_logs(user=Depends(get_current_user)):
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        cursor.execute("SELECT id FROM athletes WHERE user_id = %s", (user["id"],))
        athlete = cursor.fetchone()
        if not athlete:
            raise HTTPException(status_code=404, detail="Athlete not found")

        cursor.execute("""
            SELECT id, meet_name, meet_date, event_name, result_time, created_at
            FROM performance_logs
            WHERE athlete_id = %s
            ORDER BY created_at DESC
        """, (athlete["id"],))

        logs = cursor.fetchall()

        # Clean up result_time without conversion for consistency
        for log in logs:
            if log['result_time'] is not None:
                log['result_time'] = safe_time_conversion(log['result_time'])
            else:
                log['result_time'] = ""

        print(f"✅ Retrieved {len(logs)} performance logs for athlete {athlete['id']}")
        
        # ✅ FIXED: Return direct array, not nested success object
        return logs if logs else []

    except Exception as e:
        print("❌ DB Query Error:", e)
        raise HTTPException(status_code=500, detail=f"Failed to fetch performance logs: {str(e)}")
    finally:
        cursor.close()
        conn.close()