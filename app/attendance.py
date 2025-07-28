from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.concurrency import run_in_threadpool
from app.deps import get_current_user
from app.database import get_db_cursor
from app.utils.auth_utils import can_access_branch
from pydantic import BaseModel
from datetime import date, timedelta
import traceback
import json
import time

router = APIRouter()

WEEKDAY_MAP = {
    "Mon": 0,
    "Tue": 1,
    "Wed": 2,
    "Thu": 3,
    "Fri": 4,
    "Sat": 5,
    "Sun": 6,
}

def get_branch_session_dates(practice_days_str: str) -> list[str]:
    today = date.today()
    offset = (today.weekday() - 4) % 7  # Last Friday
    last_friday = today - timedelta(days=offset)

    # Safely split by commas to extract day names
    extracted_days = []
    for entry in practice_days_str.split(","):
        parts = entry.strip().split(":")
        if parts:
            weekday_part = parts[0].strip()
            # Match day names to known weekday map (e.g., Sat, Mon, etc.)
            for key in WEEKDAY_MAP:
                if key.lower() in weekday_part.lower():
                    extracted_days.append(key)
                    break

    session_dates = []
    for day in extracted_days[:3]:  # limit to 3
        weekday_num = WEEKDAY_MAP[day]
        delta = (weekday_num - 4) % 7
        session_date = last_friday + timedelta(days=delta)
        session_dates.append(session_date.isoformat())

    return session_dates

class AttendanceMark(BaseModel):
    athlete_id: int
    session_date: str
    status: str
    notes: str = None

def _fetch_attendance_sync_optimized(branch_id: int, session_date: str, user_id: int):
    """
    OPTIMIZED VERSION - Reduces from 4+ queries to 1-2 queries total
    """
    start_time = time.time()
    
    with get_db_cursor() as (cursor, connection):
        try:
            # SINGLE QUERY - Get all athletes with their existing attendance
            cursor.execute("""
                SELECT 
                    a.id AS athlete_id, 
                    u.name AS athlete_name,
                    att.status,
                    att.notes
                FROM athletes a
                JOIN users u ON a.user_id = u.id
                LEFT JOIN attendance att ON att.athlete_id = a.id 
                    AND att.session_date = %s AND att.branch_id = %s
                WHERE u.branch_id = %s AND u.approved = 1
                ORDER BY u.name
            """, (session_date, branch_id, branch_id))
            
            results = cursor.fetchall()
            
            # Collect athletes without attendance records
            missing_athletes = []
            for r in results:
                if r["status"] is None:
                    missing_athletes.append((r["athlete_id"], session_date, branch_id, user_id))
            
            # BULK INSERT missing records (if any)
            if missing_athletes:
                cursor.executemany("""
                    INSERT INTO attendance (athlete_id, session_date, status, branch_id, recorded_by)
                    VALUES (%s, %s, NULL, %s, %s)
                    ON DUPLICATE KEY UPDATE status = status
                """, missing_athletes)
                connection.commit()
            
            execution_time = time.time() - start_time
            print(f"⚡ OPTIMIZED attendance fetch: {execution_time:.3f}s ({len(results)} athletes)")
            
            return results
            
        except Exception as e:
            connection.rollback()
            print(f"❌ Error in optimized attendance fetch: {e}")
            raise

def _mark_attendance_sync_optimized(data: AttendanceMark, user: dict):
    """
    OPTIMIZED VERSION - Single query with built-in permission check
    """
    start_time = time.time()
    
    with get_db_cursor() as (cursor, connection):
        try:
            # Single query that does permission check AND insert/update
            cursor.execute("""
                INSERT INTO attendance (athlete_id, session_date, status, branch_id, recorded_by, notes)
                SELECT %s, %s, %s, u.branch_id, %s, %s
                FROM athletes a
                JOIN users u ON a.user_id = u.id
                WHERE a.id = %s AND u.branch_id = %s
                ON DUPLICATE KEY UPDATE 
                    status = VALUES(status), 
                    recorded_by = VALUES(recorded_by),
                    notes = VALUES(notes)
            """, (
                data.athlete_id, 
                data.session_date, 
                data.status, 
                user["id"], 
                data.notes,
                data.athlete_id, 
                user["branch_id"]
            ))
            
            if cursor.rowcount == 0:
                raise HTTPException(
                    status_code=403, 
                    detail="Athlete not found or you can only mark attendance for athletes in your branch"
                )
            
            connection.commit()
            
            execution_time = time.time() - start_time
            print(f"⚡ OPTIMIZED attendance mark: {execution_time:.3f}s")
            print(f"   athlete_id={data.athlete_id}, date={data.session_date}, status={data.status}")
            
            return {"message": "Attendance updated successfully"}
            
        except HTTPException:
            connection.rollback()
            raise
        except Exception as e:
            connection.rollback()
            print(f"❌ Error in optimized attendance marking: {e}")
            raise

def get_athlete_monthly_attendance_optimized(
    athlete_id: int, 
    year: int, 
    month: int, 
    requesting_user: dict
):
    """
    OPTIMIZED VERSION - Single query with built-in permission checking
    """
    start_time = time.time()
    
    with get_db_cursor() as (cursor, connection):
        try:
            # SINGLE QUERY with permission check and data fetch
            cursor.execute("""
                SELECT 
                    att.session_date, 
                    att.status, 
                    att.notes,
                    u.branch_id,
                    u.id as athlete_user_id
                FROM attendance att
                JOIN athletes a ON att.athlete_id = a.id
                JOIN users u ON a.user_id = u.id
                WHERE att.athlete_id = %s
                  AND YEAR(att.session_date) = %s
                  AND MONTH(att.session_date) = %s
                ORDER BY att.session_date ASC
            """, (athlete_id, year, month))
            
            records = cursor.fetchall()
            
            # Permission checking
            if records:
                athlete_user_id = records[0]['athlete_user_id']
                athlete_branch_id = records[0]['branch_id']
                
                # Check permissions
                if requesting_user["role"] == "athlete":
                    if requesting_user["id"] != athlete_user_id:
                        raise HTTPException(status_code=403, detail="Access denied")
                elif requesting_user["role"] in ["coach", "head_coach"]:
                    if requesting_user["branch_id"] != athlete_branch_id:
                        raise HTTPException(status_code=403, detail="You can't access athletes from other branches")
            else:
                # If no records, still need to verify athlete exists and check permissions
                cursor.execute("""
                    SELECT u.branch_id, u.id as athlete_user_id
                    FROM athletes a
                    JOIN users u ON a.user_id = u.id
                    WHERE a.id = %s
                """, (athlete_id,))
                athlete_info = cursor.fetchone()
                
                if not athlete_info:
                    raise HTTPException(status_code=404, detail="Athlete not found")
                
                # Same permission checks
                if requesting_user["role"] == "athlete":
                    if requesting_user["id"] != athlete_info['athlete_user_id']:
                        raise HTTPException(status_code=403, detail="Access denied")
                elif requesting_user["role"] in ["coach", "head_coach"]:
                    if requesting_user["branch_id"] != athlete_info['branch_id']:
                        raise HTTPException(status_code=403, detail="Access denied")
            
            execution_time = time.time() - start_time
            print(f"⚡ OPTIMIZED monthly attendance: {execution_time:.3f}s ({len(records)} records)")
            
            return {
                "athlete_id": athlete_id,
                "year": year,
                "month": month,
                "attendance": [
                    {
                        "session_date": r["session_date"], 
                        "status": r["status"], 
                        "notes": r["notes"]
                    } for r in records
                ]
            }
            
        except HTTPException:
            raise
        except Exception as e:
            print(f"❌ Error in optimized monthly attendance: {e}")
            raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/weekly/session-dates")
def get_weekly_session_dates(user=Depends(get_current_user)):
    """Get session dates for the current user's branch"""
    with get_db_cursor() as (cursor, connection):
        try:
            # Get the user's branch_id
            branch_id = user["branch_id"]
            if not branch_id:
                raise HTTPException(status_code=400, detail="User has no branch assigned")
            
            # Get practice days for the branch
            cursor.execute("SELECT practice_days FROM branches WHERE id = %s", (branch_id,))
            row = cursor.fetchone()
            
            if not row or not row["practice_days"]:
                raise HTTPException(status_code=404, detail="Practice days not set for this branch")

            return get_branch_session_dates(row["practice_days"])
        except HTTPException:
            raise
        except Exception as e:
            print(f"❌ Error getting session dates: {e}")
            raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/branch/{branch_id}/session-dates")
def get_branch_session_dates_api(branch_id: int, user=Depends(get_current_user)):
    """Get session dates for a specific branch"""
    can_access_branch(user, branch_id)
    
    with get_db_cursor() as (cursor, connection):
        try:
            cursor.execute("SELECT practice_days FROM branches WHERE id = %s", (branch_id,))
            row = cursor.fetchone()
            
            if not row or not row["practice_days"]:
                raise HTTPException(status_code=404, detail="Practice days not set")

            return get_branch_session_dates(row["practice_days"])
        except HTTPException:
            raise
        except Exception as e:
            print(f"❌ Error getting branch session dates: {e}")
            raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/day/{session_date}")
async def get_day_attendance(session_date: str, user=Depends(get_current_user)):
    """Get attendance for a specific day for the current user's branch - OPTIMIZED"""
    branch_id = user["branch_id"]
    if not branch_id:
        raise HTTPException(status_code=400, detail="User has no branch assigned")
    
    return await run_in_threadpool(_fetch_attendance_sync_optimized, branch_id, session_date, user["id"])

@router.get("/branch/{branch_id}/day/{session_date}")
async def get_attendance_by_day(branch_id: int, session_date: str, user=Depends(get_current_user)):
    """Get attendance for a specific day and branch - OPTIMIZED"""
    can_access_branch(user, branch_id)
    return await run_in_threadpool(_fetch_attendance_sync_optimized, branch_id, session_date, user["id"])

@router.post("/mark")
async def mark_attendance(data: AttendanceMark, user=Depends(get_current_user)):
    """Mark attendance for an athlete - OPTIMIZED"""
    if user["role"] not in ["coach", "head_coach"]:
        raise HTTPException(status_code=403, detail="Only coaches can mark attendance")
    return await run_in_threadpool(_mark_attendance_sync_optimized, data, user)

@router.get("/athlete/{user_id}/week")
def get_athlete_weekly_attendance(user_id: int, user=Depends(get_current_user)):
    """Get weekly attendance for an athlete - OPTIMIZED"""
    # Allow athletes to access their own data OR coaches/head_coaches to access any athlete in their branch
    if user["id"] != user_id and user["role"] not in ["coach", "head_coach"]:
        raise HTTPException(status_code=403, detail="Access denied")

    with get_db_cursor() as (cursor, connection):
        try:
            # Single query to get athlete info and branch
            cursor.execute("""
                SELECT a.id AS athlete_id, u.branch_id, b.practice_days
                FROM athletes a
                JOIN users u ON a.user_id = u.id
                JOIN branches b ON u.branch_id = b.id
                WHERE u.id = %s
            """, (user_id,))
            result = cursor.fetchone()

            if not result:
                raise HTTPException(status_code=404, detail="Athlete profile not found")

            athlete_id = result["athlete_id"]
            branch_id = result["branch_id"]
            practice_days = result["practice_days"]

            # Additional check: if user is coach/head_coach, ensure they're in the same branch
            if user["role"] in ["coach", "head_coach"] and user["id"] != user_id:
                if user["branch_id"] != branch_id:
                    raise HTTPException(status_code=403, detail="Cannot access athletes from other branches")

            if not practice_days:
                raise HTTPException(status_code=400, detail="Branch has no practice days configured")

            session_dates = get_branch_session_dates(practice_days)

            # Single query to get all attendance records for the week
            if session_dates:
                placeholders = ', '.join(['%s'] * len(session_dates))
                cursor.execute(f"""
                    SELECT session_date, status
                    FROM attendance
                    WHERE athlete_id = %s AND session_date IN ({placeholders})
                    ORDER BY session_date
                """, [athlete_id] + session_dates)
                
                attendance_records = {row['session_date'].isoformat(): row['status'] for row in cursor.fetchall()}
            else:
                attendance_records = {}

            # Build response
            records = []
            for i, session_date in enumerate(session_dates):
                status = attendance_records.get(session_date, None)
                records.append({"day_number": i + 1, "status": status})

            return records

        except HTTPException:
            raise
        except Exception as e:
            print(f"🔍 DEBUG - Attendance error for user {user_id}:")
            print(f"   - User role: {user['role']}")
            print(f"   - User ID: {user['id']}")
            print(f"   - User branch: {user['branch_id']}")
            print(f"   - Error: {str(e)}")
            raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/branch/{branch_id}/summary")
def get_attendance_summary(branch_id: int, user=Depends(get_current_user)):
    """Get attendance summary for a branch - OPTIMIZED"""
    can_access_branch(user, branch_id)

    with get_db_cursor() as (cursor, connection):
        try:
            # Get practice days and session dates
            cursor.execute("SELECT practice_days FROM branches WHERE id = %s", (branch_id,))
            branch = cursor.fetchone()
            if not branch or not branch["practice_days"]:
                raise HTTPException(status_code=404, detail="Practice days not set")

            session_dates = get_branch_session_dates(branch["practice_days"])

            # Single optimized query
            placeholders = ', '.join(['%s'] * len(session_dates))
            cursor.execute(f"""
                SELECT 
                    a.id AS athlete_id,
                    u.name AS athlete_name,
                    u.email,
                    at.session_date,
                    at.status
                FROM athletes a
                JOIN users u ON a.user_id = u.id
                LEFT JOIN attendance at ON at.athlete_id = a.id 
                    AND at.branch_id = %s 
                    AND at.session_date IN ({placeholders})
                WHERE u.branch_id = %s AND u.approved = 1
                ORDER BY u.name, at.session_date
            """, [branch_id] + session_dates + [branch_id])
            
            rows = cursor.fetchall()

            return {
                "records": rows,
                "session_dates": session_dates
            }
        except HTTPException:
            raise
        except Exception as e:
            print(f"❌ Error getting attendance summary: {e}")
            raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/athlete/{athlete_id}/monthly")
def get_athlete_monthly_attendance(
    athlete_id: int,
    year: int = Query(..., description="Year, e.g. 2024"),
    month: int = Query(..., description="Month, e.g. 7"),
    user=Depends(get_current_user),
):
    """Get monthly attendance for an athlete - OPTIMIZED"""
    return get_athlete_monthly_attendance_optimized(athlete_id, year, month, user)

@router.get("/athlete/{athlete_id}/stats")
def get_athlete_attendance_stats(
    athlete_id: int,
    year: int = Query(..., description="Year, e.g. 2024"),
    user=Depends(get_current_user),
):
    """Get attendance statistics for an athlete for a given year - OPTIMIZED"""
    with get_db_cursor() as (cursor, connection):
        try:
            # Single query with permission check and stats calculation
            cursor.execute("""
                SELECT 
                    u.branch_id,
                    u.id as athlete_user_id,
                    COUNT(att.id) as total_sessions,
                    SUM(CASE WHEN att.status = 'present' THEN 1 ELSE 0 END) as present_count,
                    SUM(CASE WHEN att.status = 'absent' THEN 1 ELSE 0 END) as absent_count,
                    ROUND(
                        (SUM(CASE WHEN att.status = 'present' THEN 1 ELSE 0 END) / 
                         NULLIF(COUNT(CASE WHEN att.status IS NOT NULL THEN 1 END), 0)) * 100, 
                        2
                    ) as attendance_rate
                FROM athletes a
                JOIN users u ON a.user_id = u.id
                LEFT JOIN attendance att ON a.id = att.athlete_id 
                    AND YEAR(att.session_date) = %s
                    AND att.status IS NOT NULL
                WHERE a.id = %s
                GROUP BY u.branch_id, u.id
            """, (year, athlete_id))
            
            stats_result = cursor.fetchone()
            
            if not stats_result:
                raise HTTPException(status_code=404, detail="Athlete not found")
            
            branch_id = stats_result["branch_id"]
            athlete_user_id = stats_result["athlete_user_id"]

            # Check access permissions
            if user["role"] == "athlete":
                if user["id"] != athlete_user_id:
                    raise HTTPException(status_code=403, detail="Access denied")
            elif user["role"] in ["coach", "head_coach"]:
                if user["branch_id"] != branch_id:
                    raise HTTPException(status_code=403, detail="You can't access athletes from other branches")

            # Get monthly breakdown
            cursor.execute("""
                SELECT 
                    MONTH(session_date) as month,
                    COUNT(*) as total_sessions,
                    SUM(CASE WHEN status = 'present' THEN 1 ELSE 0 END) as present_count,
                    SUM(CASE WHEN status = 'absent' THEN 1 ELSE 0 END) as absent_count
                FROM attendance
                WHERE athlete_id = %s
                  AND YEAR(session_date) = %s
                  AND status IS NOT NULL
                GROUP BY MONTH(session_date)
                ORDER BY month
            """, (athlete_id, year))
            monthly_stats = cursor.fetchall()
            
            # Clean up the stats result (remove internal fields)
            clean_stats = {
                "total_sessions": stats_result["total_sessions"],
                "present_count": stats_result["present_count"],
                "absent_count": stats_result["absent_count"],
                "attendance_rate": stats_result["attendance_rate"]
            }
            
            return {
                "athlete_id": athlete_id,
                "year": year,
                "overall_stats": clean_stats,
                "monthly_breakdown": monthly_stats
            }
        except HTTPException:
            raise
        except Exception as e:
            print(f"❌ Error getting athlete attendance stats: {e}")
            raise HTTPException(status_code=500, detail="Internal server error")