# app/optimized_queries.py - Drop-in replacements for slow functions
from app.database import get_db_cursor
from fastapi import HTTPException
from app.attendance import AttendanceMark  # Import your existing model
import time

def _fetch_attendance_sync_optimized(branch_id: int, session_date: str, user_id: int):
    """
    OPTIMIZED VERSION of _fetch_attendance_sync
    Reduces from 4+ queries to 1-2 queries total
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

def get_athlete_monthly_attendance_optimized(
    athlete_id: int, 
    year: int, 
    month: int, 
    requesting_user: dict
):
    """
    OPTIMIZED VERSION of get_athlete_monthly_attendance
    Single query with built-in permission checking
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

def get_all_athletes_optimized(user_branch_id: int):
    """
    OPTIMIZED VERSION of get_all_athletes
    Single query with attendance statistics
    """
    start_time = time.time()
    
    with get_db_cursor() as (cursor, connection):
        try:
            cursor.execute("""
                SELECT 
                    a.id as athlete_id,
                    u.id as user_id,
                    u.name,
                    u.email,
                    u.branch_id,
                    u.approved,
                    COUNT(att.id) as total_sessions,
                    MAX(att.session_date) as last_attendance,
                    SUM(CASE WHEN att.status = 'present' THEN 1 ELSE 0 END) as present_count
                FROM athletes a
                JOIN users u ON a.user_id = u.id
                LEFT JOIN attendance att ON a.id = att.athlete_id
                WHERE u.branch_id = %s AND u.approved = 1
                GROUP BY a.id, u.id, u.name, u.email, u.branch_id, u.approved
                ORDER BY u.name
            """, (user_branch_id,))
            
            athletes = cursor.fetchall()
            
            execution_time = time.time() - start_time
            print(f"⚡ OPTIMIZED athletes list: {execution_time:.3f}s ({len(athletes)} athletes)")
            
            return athletes
            
        except Exception as e:
            print(f"❌ Error in optimized athletes list: {e}")
            raise

def _mark_attendance_sync_optimized(data: AttendanceMark, user: dict):
    """
    OPTIMIZED VERSION of _mark_attendance_sync
    Single query with built-in permission check
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

def get_athlete_dashboard_optimized(user: dict):
    """
    OPTIMIZED VERSION of get_athlete_dashboard
    Single query for all dashboard data
    """
    start_time = time.time()
    
    with get_db_cursor() as (cursor, connection):
        try:
            cursor.execute("""
                SELECT 
                    -- Latest attendance data
                    att.status as attendance_status,
                    att.session_date as attendance_date,
                    
                    -- Latest gear message
                    gear_post.message as gear_message,
                    
                    -- Latest thread title
                    latest_thread.title as latest_thread_title
                    
                FROM users u
                LEFT JOIN athletes a ON u.id = a.user_id
                LEFT JOIN attendance att ON a.id = att.athlete_id 
                    AND att.session_date = (
                        SELECT MAX(session_date) 
                        FROM attendance 
                        WHERE athlete_id = a.id
                    )
                LEFT JOIN (
                    SELECT p.message, t.branch_id
                    FROM posts p
                    JOIN threads t ON p.thread_id = t.id
                    WHERE t.title = 'gear'
                    ORDER BY p.created_at DESC
                    LIMIT 1
                ) gear_post ON gear_post.branch_id = u.branch_id
                LEFT JOIN (
                    SELECT title, branch_id
                    FROM threads 
                    WHERE branch_id = u.branch_id
                    ORDER BY id DESC 
                    LIMIT 1
                ) latest_thread ON latest_thread.branch_id = u.branch_id
                
                WHERE u.id = %s
            """, (user["id"],))
            
            result = cursor.fetchone()
            
            execution_time = time.time() - start_time
            print(f"⚡ OPTIMIZED dashboard: {execution_time:.3f}s")
            
            if not result:
                return {
                    "attendance": {},
                    "gear": None,
                    "latest_thread": "No threads yet"
                }
            
            return {
                "attendance": {
                    "status": result["attendance_status"],
                    "session_date": result["attendance_date"]
                } if result["attendance_status"] else {},
                "gear": result["gear_message"],
                "latest_thread": result["latest_thread_title"] or "No threads yet"
            }
            
        except Exception as e:
            print(f"❌ Error in optimized dashboard: {e}")
            raise HTTPException(status_code=500, detail="Internal server error")