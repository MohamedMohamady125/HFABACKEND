from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from app import auth, users, branches, gear, threads, payments, notifications, attendance
from app.middleware.logging import LoggingMiddleware
from app import athlete
from app import performance
from app import measurements
from app import coach
from app import head_coach
from app import coach_assignments
from app.performance import replace_all_performance_logs, ReplaceAllLogsInput
from app.deps import get_current_user
from dotenv import load_dotenv
load_dotenv()


app = FastAPI()

# ✅ Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Replace with specific origin(s) in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ✅ Add custom logging middleware
app.add_middleware(LoggingMiddleware)

# ✅ Register routers
app.include_router(auth.router, prefix="/auth", tags=["auth"])
app.include_router(head_coach.router, prefix="/head-coach", tags=["head_coach"])
app.include_router(measurements.router, prefix="/athlete", tags=["measurements"])
app.include_router(performance.router, prefix="/athlete", tags=["performance"])
app.include_router(users.router, prefix="/users", tags=["users"])
app.include_router(branches.router, prefix="/branches", tags=["branches"])
app.include_router(coach_assignments.router, prefix="/coaches", tags=["coach-assignments"])
app.include_router(gear.router, prefix="/gear", tags=["gear"])
app.include_router(threads.router, prefix="/threads", tags=["threads"])
app.include_router(payments.router, prefix="/payments", tags=["payments"])
app.include_router(notifications.router, prefix="/notifications", tags=["notifications"])
app.include_router(attendance.router, prefix="/attendance", tags=["attendance"])
app.include_router(athlete.router, tags=["athlete"])
app.include_router(coach.router, prefix="/coach", tags=["coach"])


# ✅ PERFORMANCE LOGS BY ATHLETE ID - WORKING
@app.get("/athletes/{athlete_id}/performance-logs", tags=["performance"])
async def get_athlete_performance_logs_by_id(
    athlete_id: int,
    user=Depends(get_current_user)
):
    """
    Get performance logs for a specific athlete.
    Only coaches can access this endpoint.
    """
    # Only coaches can view athlete performance logs
    if user["role"] not in ["coach", "head_coach"]:
        raise HTTPException(
            status_code=403, 
            detail="Only coaches can view athlete performance logs"
        )

    from app.database import get_connection
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        print(f"🔄 Looking for athlete with athlete_id: {athlete_id}")
        
        # ✅ Query by athlete table ID directly
        cursor.execute("""
            SELECT 
                a.id as athlete_table_id,
                u.branch_id, 
                u.name as athlete_name,
                u.id as user_id
            FROM athletes a
            JOIN users u ON a.user_id = u.id
            WHERE a.id = %s
        """, (athlete_id,))
        
        athlete = cursor.fetchone()
        
        if not athlete:
            print(f"❌ No athlete found with athlete_id: {athlete_id}")
            raise HTTPException(status_code=404, detail=f"Athlete not found with ID: {athlete_id}")

        print(f"✅ Found athlete: {athlete}")

        # Check branch access for regular coaches
        if user["role"] == "coach" and user["branch_id"] != athlete["branch_id"]:
            raise HTTPException(
                status_code=403, 
                detail="You can only view athletes from your branch"
            )

        # Get performance logs using the athlete table ID
        athlete_table_id = athlete["athlete_table_id"]
        
        print(f"🔄 Getting performance logs for athlete_table_id: {athlete_table_id}")
        
        cursor.execute("""
            SELECT 
                id, 
                meet_name, 
                meet_date, 
                event_name, 
                result_time, 
                created_at,
                athlete_id
            FROM performance_logs
            WHERE athlete_id = %s
            ORDER BY created_at DESC, meet_date DESC
        """, (athlete_table_id,))

        logs = cursor.fetchall()
        
        print(f"🔄 Found {len(logs)} performance logs")

        # Clean up result_time for consistency
        for log in logs:
            if log['result_time'] is not None:
                log['result_time'] = str(log['result_time']).strip()
            else:
                log['result_time'] = ""

        print(f"✅ Retrieved {len(logs)} performance logs for athlete {athlete_id} ({athlete['athlete_name']})")
        
        # Return direct array like the original endpoint
        return logs if logs else []

    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error getting performance logs for athlete {athlete_id}: {e}")
        raise HTTPException(
            status_code=500, 
            detail=f"Failed to fetch performance logs: {str(e)}"
        )
    finally:
        cursor.close()
        conn.close()

# ✅ NEW MEASUREMENTS ENDPOINT - FIXED
@app.get("/athletes/{athlete_id}/measurements", tags=["measurements"])
async def get_athlete_measurements_by_id(
    athlete_id: int,
    user=Depends(get_current_user)
):
    """
    Get all measurements for a specific athlete.
    Only coaches can access this endpoint.
    """
    # Only coaches can view athlete measurements
    if user["role"] not in ["coach", "head_coach"]:
        raise HTTPException(
            status_code=403, 
            detail="Only coaches can view athlete measurements"
        )

    from app.database import get_connection
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        print(f"🔄 Getting measurements for athlete ID: {athlete_id}")
        
        # Get athlete info and verify access - SAME LOGIC AS PERFORMANCE LOGS
        cursor.execute("""
            SELECT 
                a.id as athlete_table_id,
                u.branch_id, 
                u.name as athlete_name,
                u.email as athlete_email,
                u.id as user_id
            FROM athletes a
            JOIN users u ON a.user_id = u.id
            WHERE a.id = %s
        """, (athlete_id,))
        
        athlete = cursor.fetchone()
        
        if not athlete:
            print(f"❌ No athlete found with athlete_id: {athlete_id}")
            raise HTTPException(status_code=404, detail=f"Athlete not found with ID: {athlete_id}")

        print(f"✅ Found athlete: {athlete}")

        # Check branch access for regular coaches
        if user["role"] == "coach" and user["branch_id"] != athlete["branch_id"]:
            raise HTTPException(
                status_code=403, 
                detail="You can only view athletes from your branch"
            )

        # Get all measurements for this athlete using the athlete table ID
        athlete_table_id = athlete["athlete_table_id"]
        
        print(f"🔄 Getting measurements for athlete_table_id: {athlete_table_id}")
        
        cursor.execute("""
            SELECT 
                id,
                height,
                weight,
                arm,
                leg,
                fat,
                muscle,
                created_at
            FROM measurement_logs
            WHERE athlete_id = %s
            ORDER BY created_at DESC
        """, (athlete_table_id,))

        measurements = cursor.fetchall()
        
        print(f"✅ Retrieved {len(measurements)} measurements for athlete {athlete_id}")
        
        return {
            "success": True,
            "athlete": {
                "id": athlete_id,
                "name": athlete["athlete_name"],
                "email": athlete["athlete_email"]
            },
            "measurements": measurements
        }

    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error getting measurements for athlete {athlete_id}: {e}")
        raise HTTPException(
            status_code=500, 
            detail=f"Failed to fetch measurements: {str(e)}"
        )
    finally:
        cursor.close()
        conn.close()

# Add this to your main.py file or create a new athlete.py router

# Replace your /athlete/me endpoint in main.py with this enhanced version:

@app.get("/athlete/me", tags=["athlete"])
async def get_current_athlete_info(user=Depends(get_current_user)):
    """
    Get current athlete's information including athlete table ID.
    Only athletes can access this endpoint.
    """
    print(f"🔄 /athlete/me called by user: {user}")
    print(f"🔄 User role: {user.get('role')}")
    print(f"🔄 User ID: {user.get('id')}")
    
    if user["role"] != "athlete":
        print(f"❌ Access denied - user role is {user['role']}, not 'athlete'")
        raise HTTPException(
            status_code=403, 
            detail="Only athletes can access this endpoint"
        )

    from app.database import get_connection
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        print(f"🔄 Getting athlete info for user ID: {user['id']}")
        
        cursor.execute("""
            SELECT 
                a.id as athlete_id,
                u.id as user_id,
                u.name,
                u.email,
                u.branch_id
            FROM athletes a
            JOIN users u ON a.user_id = u.id
            WHERE u.id = %s
        """, (user["id"],))
        
        athlete = cursor.fetchone()
        
        if not athlete:
            print(f"❌ No athlete record found for user ID: {user['id']}")
            
            # Let's check if the user exists at all
            cursor.execute("SELECT id, name, email, role FROM users WHERE id = %s", (user["id"],))
            user_check = cursor.fetchone()
            print(f"🔍 User check result: {user_check}")
            
            # Let's also see what's in the athletes table
            cursor.execute("SELECT * FROM athletes LIMIT 5")
            sample_athletes = cursor.fetchall()
            print(f"🔍 Sample athletes: {sample_athletes}")
            
            raise HTTPException(status_code=404, detail="Athlete record not found")

        print(f"✅ Found athlete: {athlete}")
        return athlete

    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error getting athlete info: {e}")
        import traceback
        print(f"❌ Full traceback: {traceback.format_exc()}")
        raise HTTPException(
            status_code=500, 
            detail=f"Failed to fetch athlete info: {str(e)}"
        )
    finally:
        cursor.close()
        conn.close()

# Add this endpoint to your measurements.py router or main.py

@app.get("/athlete/measurements", tags=["measurements"])
async def get_athlete_measurements(user=Depends(get_current_user)):
    """
    Get the latest measurements for the current athlete.
    Only athletes can access their own measurements.
    """
    if user["role"] != "athlete":
        raise HTTPException(
            status_code=403, 
            detail="Only athletes can access their measurements"
        )

    from app.database import get_connection
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        print(f"🔄 Getting measurements for user ID: {user['id']}")
        
        # First, get the athlete ID from the user ID
        cursor.execute("""
            SELECT a.id as athlete_id
            FROM athletes a
            JOIN users u ON a.user_id = u.id
            WHERE u.id = %s
        """, (user["id"],))
        
        athlete_record = cursor.fetchone()
        
        if not athlete_record:
            print(f"❌ No athlete record found for user ID: {user['id']}")
            raise HTTPException(status_code=404, detail="Athlete record not found")

        athlete_id = athlete_record["athlete_id"]
        print(f"✅ Found athlete ID: {athlete_id}")
        
        # Get the latest measurements for this athlete
        cursor.execute("""
            SELECT 
                height,
                weight,
                arm,
                leg,
                fat,
                muscle,
                created_at
            FROM measurement_logs
            WHERE athlete_id = %s
            ORDER BY created_at DESC
            LIMIT 1
        """, (athlete_id,))
        
        latest_measurement = cursor.fetchone()
        
        if latest_measurement:
            print(f"✅ Found latest measurement: {latest_measurement}")
            return latest_measurement
        else:
            print("ℹ️ No measurements found for this athlete")
            raise HTTPException(status_code=404, detail="No measurements found")

    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error getting measurements: {e}")
        raise HTTPException(
            status_code=500, 
            detail=f"Failed to fetch measurements: {str(e)}"
        )
    finally:
        cursor.close()
        conn.close()



# ✅ EXISTING ROUTE
@app.post("/athlete/performance-logs/replace-all", tags=["performance"])
async def replace_all_performance_logs_endpoint(
    data: ReplaceAllLogsInput,
    user=Depends(get_current_user)
):
    return replace_all_performance_logs(data, user)

@app.get("/")
def root():
    return {"message": "HFA API is running"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)