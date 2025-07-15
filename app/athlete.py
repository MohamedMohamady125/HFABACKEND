from fastapi import APIRouter, Depends, HTTPException
from fastapi.concurrency import run_in_threadpool # Not used in this snippet, but good to keep if used elsewhere
from pydantic import BaseModel
from typing import Optional, Dict

# Assuming these are correctly defined in your project
from app.deps import get_current_user
from app.database import get_connection

router = APIRouter()

# Pydantic models for response validation and documentation
class AthleteDashboardResponse(BaseModel):
    attendance: Dict[str, Optional[str]]
    gear: Optional[str]
    latest_thread: Optional[str]

class AthleteIdResponse(BaseModel):
    id: int

@router.get("/athlete/home", response_model=AthleteDashboardResponse)
def get_athlete_dashboard(user: dict = Depends(get_current_user)):
    """
    Retrieves dashboard data for an athlete, including recent attendance,
    latest gear message, and the most recent thread title for their branch.
    """
    if user["role"] != "athlete":
        raise HTTPException(status_code=403, detail="Access denied. Only athletes can access this dashboard.")

    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        athlete_user_id = user["id"]
        athlete_branch_id = user.get("branch_id") # Use .get() for safety

        if not athlete_branch_id:
            raise HTTPException(status_code=400, detail="Athlete's branch ID not found.")

        # Attendance (most recent)
        cursor.execute("""
            SELECT status, session_date
            FROM attendance
            WHERE athlete_id = (
                SELECT id FROM athletes WHERE user_id = %s
            )
            ORDER BY session_date DESC
            LIMIT 1
        """, (athlete_user_id,))
        attendance = cursor.fetchone()

        # Gear (assuming 'gear' is a thread title and message is in posts)
        cursor.execute("""
            SELECT p.message
            FROM posts p
            JOIN threads t ON p.thread_id = t.id
            WHERE t.branch_id = %s AND t.title = 'gear'
            ORDER BY p.created_at DESC
            LIMIT 1
        """, (athlete_branch_id,)) # Use athlete_branch_id
        gear = cursor.fetchone()

        # Latest thread
        cursor.execute("""
            SELECT title FROM threads WHERE branch_id = %s
            ORDER BY id DESC LIMIT 1
        """, (athlete_branch_id,)) # Use athlete_branch_id
        thread = cursor.fetchone()

        return {
            "attendance": attendance if attendance else {}, # Return empty dict if no attendance
            "gear": gear["message"] if gear else None,
            "latest_thread": thread["title"] if thread else "No threads yet"
        }

    except HTTPException:
        # Re-raise HTTPExceptions directly
        raise
    except Exception as e:
        # Log the unexpected error and raise a generic HTTP 500
        print(f"An unexpected error occurred in /athlete/home: {e}")
        raise HTTPException(status_code=500, detail="Internal server error.")
    finally:
        cursor.close()
        conn.close()

@router.get("/athletes/user/{user_id}", response_model=AthleteIdResponse)
def get_athlete_by_user(user_id: int, user: dict = Depends(get_current_user)):
    """
    Retrieves the athlete ID given a user ID.
    Accessible by any authenticated user (consider adding more specific roles if needed).
    """
    # Optional: Add authorization check if only specific roles can query athlete by user_id
    # For example: if user["role"] not in ["coach", "head_coach", "admin"] and user["id"] != user_id:
    #     raise HTTPException(status_code=403, detail="Access denied")

    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("SELECT id FROM athletes WHERE user_id = %s", (user_id,))
        athlete = cursor.fetchone()
        if not athlete:
            raise HTTPException(status_code=404, detail="Athlete not found for the given user ID.")
        return athlete
    except HTTPException:
        raise # Re-raise HTTPExceptions directly
    except Exception as e:
        print(f"An unexpected error occurred in /athletes/user/{user_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error.")
    finally:
        cursor.close()
        conn.close()

@router.get("/athletes/all")
def get_all_athletes(user: dict = Depends(get_current_user)):
    """Get all athletes with proper athlete_id for attendance tracking"""
    if user["role"] not in ["coach", "head_coach"]:
        raise HTTPException(status_code=403, detail="Access denied")
    
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    
    try:
        # Get athletes from the same branch as the coach
        cursor.execute("""
            SELECT 
                a.id as athlete_id,    -- This is the athletes table ID
                u.id as user_id,       -- This is the users table ID  
                u.name,
                u.email,
                u.branch_id,
                u.approved
            FROM athletes a
            JOIN users u ON a.user_id = u.id
            WHERE u.branch_id = %s AND u.approved = 1
            ORDER BY u.name
        """, (user["branch_id"],))
        
        athletes = cursor.fetchall()
        return athletes
        
    except Exception as e:
        print(f"❌ Error getting all athletes: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")
    finally:
        cursor.close()
        conn.close()

@router.delete("/athletes/{athlete_id}")
def delete_athlete(athlete_id: int, user=Depends(get_current_user)):
    """Delete an athlete and their associated user account"""
    if user["role"] not in ["coach", "head_coach"]:
        raise HTTPException(status_code=403, detail="Only coaches can delete athletes")
    
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    
    try:
        # First, get the athlete to find the associated user_id
        cursor.execute("""
            SELECT a.id, a.user_id, u.name, u.branch_id
            FROM athletes a
            JOIN users u ON a.user_id = u.id
            WHERE a.id = %s
        """, (athlete_id,))
        
        athlete = cursor.fetchone()
        if not athlete:
            raise HTTPException(status_code=404, detail="Athlete not found")
        
        # Check if the coach can delete this athlete (same branch)
        if athlete["branch_id"] != user["branch_id"]:
            raise HTTPException(status_code=403, detail="Can only delete athletes from your branch")
        
        user_id = athlete["user_id"]
        athlete_name = athlete["name"]
        
        print(f"🔄 Starting deletion process for athlete {athlete_name} (ID: {athlete_id}, User ID: {user_id})")
        
        # Delete in the correct order (due to foreign key constraints)
        # Start with tables that reference athlete_id, then move to user_id references
        
        # 1. Delete attendance records (references athlete_id)
        print(f"🔄 Deleting attendance records...")
        cursor.execute("DELETE FROM attendance WHERE athlete_id = %s", (athlete_id,))
        attendance_deleted = cursor.rowcount
        print(f"✅ Deleted {attendance_deleted} attendance records")
        
        # 2. Delete payment records (references athlete_id)
        print(f"🔄 Deleting payment records...")
        cursor.execute("DELETE FROM payments WHERE athlete_id = %s", (athlete_id,))
        payments_deleted = cursor.rowcount
        print(f"✅ Deleted {payments_deleted} payment records")
        
        # 3. Delete gear issues (references athlete_id)
        try:
            print(f"🔄 Deleting gear issues...")
            cursor.execute("DELETE FROM gear_issues WHERE athlete_id = %s", (athlete_id,))
            gear_deleted = cursor.rowcount
            print(f"✅ Deleted {gear_deleted} gear issue records")
        except Exception as gear_error:
            print(f"⚠️ Gear issues table may not exist: {gear_error}")
        
        # 4. Delete performance logs (references athlete_id)
        try:
            print(f"🔄 Deleting performance logs...")
            cursor.execute("DELETE FROM performance_logs WHERE athlete_id = %s", (athlete_id,))
            perf_deleted = cursor.rowcount
            print(f"✅ Deleted {perf_deleted} performance log records")
        except Exception as perf_error:
            print(f"⚠️ Performance logs cleanup failed: {perf_error}")
        
        # 5. Delete measurements (references athlete_id)
        try:
            print(f"🔄 Deleting measurements...")
            cursor.execute("DELETE FROM measurements WHERE athlete_id = %s", (athlete_id,))
            measurements_deleted = cursor.rowcount
            print(f"✅ Deleted {measurements_deleted} measurement records")
        except Exception as measurements_error:
            print(f"⚠️ Measurements cleanup failed: {measurements_error}")
        
        # 6. Delete notifications (references user_id) - THIS WAS MISSING!
        print(f"🔄 Deleting notifications...")
        cursor.execute("DELETE FROM notifications WHERE user_id = %s", (user_id,))
        notifications_deleted = cursor.rowcount
        print(f"✅ Deleted {notifications_deleted} notification records")
        
        # 7. Delete any posts by this user (references user_id)
        try:
            print(f"🔄 Deleting user posts...")
            cursor.execute("DELETE FROM posts WHERE user_id = %s", (user_id,))
            posts_deleted = cursor.rowcount
            print(f"✅ Deleted {posts_deleted} user posts")
        except Exception as posts_error:
            print(f"⚠️ Posts cleanup failed: {posts_error}")
        
        # 8. Delete registration requests (if any reference this user)
        try:
            print(f"🔄 Deleting registration requests...")
            cursor.execute("DELETE FROM registration_requests WHERE email = (SELECT email FROM users WHERE id = %s)", (user_id,))
            requests_deleted = cursor.rowcount
            print(f"✅ Deleted {requests_deleted} registration requests")
        except Exception as requests_error:
            print(f"⚠️ Registration requests cleanup failed: {requests_error}")
        
        # 9. Delete athlete record
        print(f"🔄 Deleting athlete record...")
        cursor.execute("DELETE FROM athletes WHERE id = %s", (athlete_id,))
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="Athlete record not found")
        print(f"✅ Deleted athlete record")
        
        # 10. Finally, delete user record (this was failing before)
        print(f"🔄 Deleting user record...")
        cursor.execute("DELETE FROM users WHERE id = %s", (user_id,))
        if cursor.rowcount == 0:
            print(f"⚠️ User record not found (ID: {user_id})")
        else:
            print(f"✅ Deleted user record")
        
        conn.commit()
        
        print(f"✅ Successfully deleted athlete {athlete_name} (ID: {athlete_id})")
        
        return {"success": True, "message": f"Athlete {athlete_name} deleted successfully"}
        
    except HTTPException:
        conn.rollback()
        raise
    except Exception as e:
        conn.rollback()
        print(f"❌ Detailed error deleting athlete {athlete_id}: {str(e)}")
        print(f"❌ Error type: {type(e).__name__}")
        import traceback
        print(f"❌ Full traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Failed to delete athlete: {str(e)}")
    finally:
        cursor.close()
        conn.close()