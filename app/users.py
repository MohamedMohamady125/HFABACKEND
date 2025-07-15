from fastapi import APIRouter, Depends, HTTPException
from app.database import get_connection
from app.deps import get_current_user
from passlib.hash import bcrypt
from datetime import date, datetime
import json
from pydantic import BaseModel

router = APIRouter()

class PaymentMark(BaseModel):
    athlete_id: int
    session_date: str  # actual training session
    status: str  # 'paid', 'pending', 'late'

@router.get("/me")
def get_current_user_details(user=Depends(get_current_user)):
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    # Always get branch_id from users table for current context
    cursor.execute("SELECT branch_id FROM users WHERE id = %s", (user["id"],))
    branch_row = cursor.fetchone()
    branch_id = branch_row["branch_id"] if branch_row else None

    # Get branch name from branches table
    cursor.execute("SELECT name FROM branches WHERE id = %s", (branch_id,))
    branch = cursor.fetchone()
    branch_name = branch["name"] if branch else None

    cursor.close()
    conn.close()

    return {
        "id": user["id"],
        "name": user["name"],
        "email": user["email"],
        "phone": user["phone"],
        "role": user["role"],
        "approved": bool(user.get("approved", False)),
        "branch_id": branch_id,
        "branch_name": branch_name,
    }



@router.post("/payments/mark")
def mark_payment(data: PaymentMark, user=Depends(get_current_user)):
    if user["role"] not in ["coach", "head_coach"]:
        raise HTTPException(status_code=403, detail="Only coaches can update payments")

    conn = get_connection()
    cursor = conn.cursor()

    try:
        session_dt = datetime.strptime(data.session_date, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid session_date format")

    due_date = session_dt.replace(day=1)

    cursor.execute("""
        INSERT INTO payments (athlete_id, session_date, due_date, branch_id, status, confirmed_by_coach)
        VALUES (%s, %s, %s, %s, %s, TRUE)
        ON DUPLICATE KEY UPDATE status = VALUES(status), confirmed_by_coach = TRUE
    """, (
        data.athlete_id,
        session_dt,
        due_date,
        user["branch_id"],
        data.status,
    ))

    conn.commit()
    return {"message": "Payment status updated"}

# Replace the registration requests endpoints in your users.py with these branch-filtered versions:

# Replace the /requests endpoint in your users.py with this debug version:

@router.get("/requests")
def get_registration_requests(user=Depends(get_current_user)):
    """
    Get registration requests filtered by coach's branch.
    Coaches can only see requests for their own branch.
    Head coaches can see requests for all branches.
    """
    if user["role"] not in ["coach", "head_coach"]:
        raise HTTPException(status_code=403, detail="Only coaches can view registration requests")

    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    
    try:
        print(f"🔍 DEBUG - Registration requests query:")
        print(f"   - User: {user['name']} (ID: {user['id']})")
        print(f"   - Role: {user['role']}")
        print(f"   - Branch ID: {user['branch_id']}")
        
        if user["role"] == "head_coach":
            # Head coaches can see ALL registration requests
            cursor.execute("""
                SELECT id, athlete_name, phone, email, branch_name, submitted_at, approved
                FROM registration_requests
                WHERE approved = 0
                ORDER BY submitted_at DESC
            """)
            print(f"✅ Head coach {user['name']} viewing ALL registration requests")
        else:
            # Regular coaches can only see requests for their branch
            # First get the coach's branch name
            cursor.execute("SELECT name FROM branches WHERE id = %s", (user["branch_id"],))
            branch_info = cursor.fetchone()
            
            if not branch_info:
                print(f"❌ No branch found for branch_id: {user['branch_id']}")
                raise HTTPException(status_code=400, detail="Coach branch not found")
            
            coach_branch_name = branch_info["name"]
            print(f"   - Coach's Branch Name: {coach_branch_name}")
            
            # Get only requests for this coach's branch
            cursor.execute("""
                SELECT id, athlete_name, phone, email, branch_name, submitted_at, approved
                FROM registration_requests
                WHERE approved = 0 AND branch_name = %s
                ORDER BY submitted_at DESC
            """, (coach_branch_name,))
            
            print(f"✅ Coach {user['name']} viewing registration requests for {coach_branch_name} branch ONLY")
            print(f"   - SQL Query: SELECT ... WHERE approved = 0 AND branch_name = '{coach_branch_name}'")
        
        requests = cursor.fetchall()
        print(f"✅ Found {len(requests)} pending registration requests")
        
        # ✅ DEBUG: Print each request to see what's being returned
        for i, request in enumerate(requests):
            print(f"   Request {i+1}: {request['athlete_name']} -> {request['branch_name']} branch")
        
        return requests
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error getting registration requests: {e}")
        import traceback
        print(f"❌ Full traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail="Failed to get registration requests")
    finally:
        cursor.close()
        conn.close()

# Replace the approve endpoint in your users.py with this fixed version:

@router.post("/approve/{request_id}")
def approve_registration_request(request_id: int, user=Depends(get_current_user)):
    """
    Approve registration request with branch validation.
    Coaches can only approve requests for their own branch.
    Head coaches can approve any request.
    """
    if user["role"] not in ["coach", "head_coach"]:
        raise HTTPException(status_code=403, detail="Only coaches can approve registrations")

    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        # Step 1: Fetch registration request
        cursor.execute("SELECT * FROM registration_requests WHERE id = %s", (request_id,))
        request = cursor.fetchone()
        if not request:
            raise HTTPException(status_code=404, detail="Request not found")

        print(f"🔍 DEBUG - Registration request details:")
        print(f"   - Request ID: {request_id}")
        print(f"   - Athlete: {request['athlete_name']}")
        print(f"   - Requested Branch: {request['branch_name']}")
        print(f"   - Coach: {user['name']} (ID: {user['id']})")
        print(f"   - Coach Role: {user['role']}")

        # Step 2: Branch validation for regular coaches
        if user["role"] == "coach":
            # Get coach's branch name
            cursor.execute("SELECT name FROM branches WHERE id = %s", (user["branch_id"],))
            branch_info = cursor.fetchone()
            
            if not branch_info:
                raise HTTPException(status_code=400, detail="Coach branch not found")
            
            coach_branch_name = branch_info["name"]
            print(f"   - Coach's Branch: {coach_branch_name}")
            
            # ✅ CRITICAL CHECK: Ensure request is for coach's branch
            if request["branch_name"] != coach_branch_name:
                print(f"❌ BRANCH MISMATCH!")
                print(f"   - Request for: {request['branch_name']}")
                print(f"   - Coach manages: {coach_branch_name}")
                raise HTTPException(
                    status_code=403, 
                    detail=f"You can only approve requests for {coach_branch_name} branch"
                )
            
            print(f"✅ Coach {user['name']} is authorized to approve request for {coach_branch_name} branch")
        else:
            print(f"✅ Head coach {user['name']} can approve request for any branch ({request['branch_name']})")

        # Step 3: Get the CORRECT branch_id from the registration request's branch name
        cursor.execute("SELECT id FROM branches WHERE name = %s", (request["branch_name"],))
        requested_branch = cursor.fetchone()
        if not requested_branch:
            raise HTTPException(status_code=400, detail=f"Branch '{request['branch_name']}' not found")
        
        requested_branch_id = requested_branch["id"]
        print(f"✅ Requested branch '{request['branch_name']}' has ID: {requested_branch_id}")

        # Step 4: Check if user already exists
        cursor.execute("SELECT * FROM users WHERE email = %s", (request["email"],))
        existing_user = cursor.fetchone()

        if existing_user:
            user_id = existing_user["id"]
            if existing_user["approved"]:
                return {"message": "User already approved"}

            # ✅ FIXED: Use the requested branch ID, not the coach's branch ID
            cursor.execute("""
                UPDATE users
                SET approved = 1, branch_id = %s
                WHERE id = %s
            """, (requested_branch_id, user_id))
            print(f"✅ Updated existing user {user_id} to branch {requested_branch_id}")
        else:
            # ✅ FIXED: Use the requested branch ID, not the coach's branch ID
            cursor.execute("""
                INSERT INTO users (name, email, phone, password_hash, role, approved, branch_id)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (
                request["athlete_name"],
                request["email"],
                request["phone"],
                request["password_hash"],
                "athlete",
                True,
                requested_branch_id  # ✅ FIXED: Use requested branch, not coach's branch
            ))
            user_id = cursor.lastrowid
            print(f"✅ Created new user {user_id} in branch {requested_branch_id}")

        # Step 5: Insert into athletes table if not already
        cursor.execute("INSERT IGNORE INTO athletes (user_id) VALUES (%s)", (user_id,))
        print(f"✅ Added athlete record for user {user_id}")

        # Step 6: Add initial payment row for current month
        cursor.execute("SELECT id FROM athletes WHERE user_id = %s", (user_id,))
        athlete = cursor.fetchone()
        if athlete:
            athlete_id = athlete["id"]
            first_of_month = date.today().replace(day=1)

            # ✅ FIXED: Use the requested branch ID for payments
            cursor.execute("""
                INSERT INTO payments (athlete_id, session_date, due_date, branch_id, status, confirmed_by_coach)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE status = VALUES(status)
            """, (
                athlete_id,
                first_of_month,
                first_of_month,
                requested_branch_id,  # ✅ FIXED: Use requested branch, not coach's branch
                "pending",
                False
            ))
            print(f"✅ Added payment record for athlete {athlete_id} in branch {requested_branch_id}")

        # Step 7: Approve the request
        if not request["approved"]:
            cursor.execute("""
                UPDATE registration_requests
                SET approved = 1, approved_by = %s
                WHERE id = %s
            """, (user["id"], request_id))

        conn.commit()
        
        print(f"✅ Registration approved by {user['name']} for {request['athlete_name']} in {request['branch_name']} branch")
        
        return {"message": f"Registration approved for {request['athlete_name']} in {request['branch_name']} branch"}

    except HTTPException:
        conn.rollback()
        raise
    except Exception as e:
        conn.rollback()
        print(f"❌ Error approving registration: {e}")
        import traceback
        print(f"❌ Full traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail="Failed to approve registration")
    finally:
        cursor.close()
        conn.close()

@router.post("/reject/{request_id}")
def reject_registration_request(request_id: int, user=Depends(get_current_user)):
    """
    Reject registration request with branch validation.
    Coaches can only reject requests for their own branch.
    Head coaches can reject any request.
    """
    if user["role"] not in ["coach", "head_coach"]:
        raise HTTPException(status_code=403, detail="Only coaches can reject registrations")

    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        # Step 1: Confirm the request exists and get details
        cursor.execute("SELECT * FROM registration_requests WHERE id = %s", (request_id,))
        request = cursor.fetchone()
        if not request:
            raise HTTPException(status_code=404, detail="Request not found")

        # Step 2: Branch validation for regular coaches
        if user["role"] == "coach":
            # Get coach's branch name
            cursor.execute("SELECT name FROM branches WHERE id = %s", (user["branch_id"],))
            branch_info = cursor.fetchone()
            
            if not branch_info:
                raise HTTPException(status_code=400, detail="Coach branch not found")
            
            coach_branch_name = branch_info["name"]
            
            # Check if request is for coach's branch
            if request["branch_name"] != coach_branch_name:
                raise HTTPException(
                    status_code=403, 
                    detail=f"You can only reject requests for {coach_branch_name} branch"
                )
            
            print(f"✅ Coach {user['name']} rejecting request for their branch: {coach_branch_name}")
        else:
            print(f"✅ Head coach {user['name']} rejecting request for {request['branch_name']} branch")

        # Step 3: Delete the request
        cursor.execute("DELETE FROM registration_requests WHERE id = %s", (request_id,))
        conn.commit()

        print(f"✅ Registration rejected by {user['name']} for {request['athlete_name']} in {request['branch_name']} branch")
        
        return {"message": f"Registration request rejected for {request['athlete_name']} in {request['branch_name']} branch"}

    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error rejecting registration: {e}")
        raise HTTPException(status_code=500, detail="Failed to reject registration")
    finally:
        cursor.close()
        conn.close()