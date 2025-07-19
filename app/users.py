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


# Add these imports at the top of your users.py file (if not already present):
import secrets
import string
from datetime import datetime, timedelta

# Add these Pydantic models after your existing models:
class CreateInviteLinkResponse(BaseModel):
    success: bool
    invite_token: str
    invite_url: str
    expires_at: str

class LoginWithInviteRequest(BaseModel):
    invite_token: str

def generate_invite_token(length=32):
    """Generate a secure random token for invite links"""
    alphabet = string.ascii_letters + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(length))

# Add these endpoints to your router in users.py:

@router.post("/invite/create")
def create_invite_link(user=Depends(get_current_user)):
    """Create a shareable invite link for the current user"""
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    
    try:
        print(f"🔗 Creating invite link for user {user['id']} ({user['name']})")
        
        # Generate unique token
        invite_token = generate_invite_token()
        
        # Set expiration time (24 hours from now)
        expires_at = datetime.now() + timedelta(hours=24)
        
        # Invalidate any existing unused invite links for this user
        cursor.execute("""
            UPDATE invite_links 
            SET invalidated_at = NOW() 
            WHERE user_id = %s AND used = 0 AND invalidated_at IS NULL
        """, (user["id"],))
        
        # Insert new invite link
        cursor.execute("""
            INSERT INTO invite_links (user_id, token, expires_at, used, created_at)
            VALUES (%s, %s, %s, 0, NOW())
        """, (user["id"], invite_token, expires_at))
        
        conn.commit()
        
        # Create the invite URL (adjust base URL as needed)
        base_url = "http://192.168.1.5:8000"  # Your local URL
        invite_url = f"{base_url}/invite/{invite_token}"
        
        print(f"✅ Invite link created: {invite_url}")
        
        return {
            "success": True,
            "invite_token": invite_token,
            "invite_url": invite_url,
            "expires_at": expires_at.isoformat()
        }
        
    except Exception as e:
        conn.rollback()
        print(f"❌ Error creating invite link: {e}")
        raise HTTPException(status_code=500, detail="Failed to create invite link")
    finally:
        cursor.close()
        conn.close()

@router.post("/invite/login")
def login_with_invite(data: LoginWithInviteRequest):
    """Login using an invite token"""
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    
    try:
        print(f"🔗 Attempting login with invite token: {data.invite_token}")
        
        # Clean up expired invite links
        cursor.execute("DELETE FROM invite_links WHERE expires_at < NOW()")
        
        # Find valid invite link
        cursor.execute("""
            SELECT il.*, u.id as user_id, u.name, u.email, u.phone, u.role, u.approved, u.branch_id
            FROM invite_links il
            JOIN users u ON il.user_id = u.id
            WHERE il.token = %s 
            AND il.used = 0 
            AND il.invalidated_at IS NULL 
            AND il.expires_at > NOW()
        """, (data.invite_token,))
        
        invite_record = cursor.fetchone()
        
        if not invite_record:
            print(f"❌ Invalid or expired invite token: {data.invite_token}")
            raise HTTPException(
                status_code=400,
                detail="Invalid or expired invite link"
            )
        
        # Mark invite link as used
        cursor.execute("""
            UPDATE invite_links 
            SET used = 1, used_at = NOW() 
            WHERE token = %s
        """, (data.invite_token,))
        
        conn.commit()
        
        # Create JWT token for the user
        from jose import jwt
        from app.config import settings
        
        token = jwt.encode(
            {"sub": str(invite_record["user_id"])},
            settings.JWT_SECRET,
            algorithm=settings.JWT_ALGORITHM,
        )
        
        print(f"✅ User {invite_record['name']} logged in via invite link")
        
        return {
            "success": True,
            "token": token,
            "user": {
                "id": invite_record["user_id"],
                "name": invite_record["name"],
                "email": invite_record["email"],
                "phone": invite_record["phone"],
                "role": invite_record["role"],
                "approved": bool(invite_record.get("approved", False)),
                "branch_id": invite_record["branch_id"],
            },
            "message": f"Successfully logged in as {invite_record['name']}"
        }
        
    except HTTPException:
        conn.rollback()
        raise
    except Exception as e:
        conn.rollback()
        print(f"❌ Error during invite login: {e}")
        raise HTTPException(status_code=500, detail="Failed to login with invite link")
    finally:
        cursor.close()
        conn.close()

@router.get("/invite/validate/{token}")
def validate_invite_token(token: str):
    """Validate an invite token without using it"""
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    
    try:
        # Clean up expired invite links
        cursor.execute("DELETE FROM invite_links WHERE expires_at < NOW()")
        
        # Check if invite link is valid
        cursor.execute("""
            SELECT il.expires_at, u.name, u.email, u.role
            FROM invite_links il
            JOIN users u ON il.user_id = u.id
            WHERE il.token = %s 
            AND il.used = 0 
            AND il.invalidated_at IS NULL 
            AND il.expires_at > NOW()
        """, (token,))
        
        invite_record = cursor.fetchone()
        
        if not invite_record:
            return {
                "valid": False,
                "message": "Invalid or expired invite link"
            }
        
        return {
            "valid": True,
            "user_name": invite_record["name"],
            "user_email": invite_record["email"],
            "user_role": invite_record["role"],
            "expires_at": invite_record["expires_at"].isoformat(),
            "message": f"Valid invite link for {invite_record['name']}"
        }
        
    except Exception as e:
        print(f"❌ Error validating invite token: {e}")
        raise HTTPException(status_code=500, detail="Failed to validate invite link")
    finally:
        cursor.close()
        conn.close()

@router.get("/invite/my-links")
def get_my_invite_links(user=Depends(get_current_user)):
    """Get all invite links created by the current user"""
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    
    try:
        # Clean up expired invite links
        cursor.execute("DELETE FROM invite_links WHERE expires_at < NOW()")
        
        # Get user's invite links
        cursor.execute("""
            SELECT token, expires_at, created_at, used, used_at, invalidated_at
            FROM invite_links
            WHERE user_id = %s
            ORDER BY created_at DESC
            LIMIT 10
        """, (user["id"],))
        
        invite_links = cursor.fetchall()
        
        return {
            "success": True,
            "invite_links": invite_links
        }
        
    except Exception as e:
        print(f"❌ Error getting invite links: {e}")
        raise HTTPException(status_code=500, detail="Failed to get invite links")
    finally:
        cursor.close()
        conn.close()

@router.delete("/invite/{token}")
def invalidate_invite_link(token: str, user=Depends(get_current_user)):
    """Invalidate a specific invite link"""
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    
    try:
        # Check if the invite link belongs to the current user
        cursor.execute("""
            SELECT id FROM invite_links 
            WHERE token = %s AND user_id = %s AND invalidated_at IS NULL
        """, (token, user["id"]))
        
        invite_link = cursor.fetchone()
        
        if not invite_link:
            raise HTTPException(
                status_code=404, 
                detail="Invite link not found or already invalidated"
            )
        
        # Invalidate the invite link
        cursor.execute("""
            UPDATE invite_links 
            SET invalidated_at = NOW() 
            WHERE token = %s
        """, (token,))
        
        conn.commit()
        
        return {
            "success": True,
            "message": "Invite link invalidated successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        conn.rollback()
        print(f"❌ Error invalidating invite link: {e}")
        raise HTTPException(status_code=500, detail="Failed to invalidate invite link")
    finally:
        cursor.close()
        conn.close()