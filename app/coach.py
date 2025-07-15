from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr
from app.deps import get_current_user
from app.database import get_connection
from passlib.hash import bcrypt

router = APIRouter()

class CoachProfile(BaseModel):
    name: str
    email: EmailStr
    branch: str

@router.get("/profile", response_model=CoachProfile)
def get_coach_profile(user=Depends(get_current_user)):
    if user["role"] not in ["coach", "head_coach"]:
        raise HTTPException(status_code=403, detail="Only coaches can access this")

    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT u.name, u.email, b.name AS branch
        FROM users u
        LEFT JOIN branches b ON u.branch_id = b.id
        WHERE u.id = %s
    """, (user["id"],))
    result = cursor.fetchone()

    cursor.close()
    conn.close()

    if not result:
        raise HTTPException(status_code=404, detail="Coach profile not found")
    return result

# ✅ Update Profile
class UpdateCoachProfile(BaseModel):
    name: str
    email: EmailStr

@router.put("/profile")
def update_coach_profile(data: UpdateCoachProfile, user=Depends(get_current_user)):
    if user["role"] not in ["coach", "head_coach"]:
        raise HTTPException(status_code=403, detail="Only coaches can update profile")

    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        UPDATE users SET name = %s, email = %s WHERE id = %s
    """, (data.name, data.email, user["id"]))
    conn.commit()

    cursor.close()
    conn.close()

    return {"message": "Profile updated successfully"}

# ✅ Change Password
class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str

@router.post("/change-password")
def change_password(data: ChangePasswordRequest, user=Depends(get_current_user)):
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT password_hash FROM users WHERE id = %s", (user["id"],))
    row = cursor.fetchone()

    if not row or not bcrypt.verify(data.old_password, row["password_hash"]):
        raise HTTPException(status_code=401, detail="Old password is incorrect")

    new_hash = bcrypt.hash(data.new_password)

    cursor.execute("UPDATE users SET password_hash = %s WHERE id = %s", (new_hash, user["id"]))
    conn.commit()

    cursor.close()
    conn.close()

    return {"message": "Password changed successfully"}

# ✅ NEW: Get assigned branches for branch switching
@router.get("/assigned-branches")
def get_coach_assigned_branches(user=Depends(get_current_user)):
    """Get branches assigned to the current coach"""
    if user["role"] not in ["coach", "head_coach"]:
        raise HTTPException(status_code=403, detail="Only coaches can access this")

    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        print(f"🔍 Getting assigned branches for {user['role']} {user['name']} (ID: {user['id']})")
        
        if user["role"] == "head_coach":
            # Head coaches can access ALL branches
            print("✅ Head coach - getting ALL branches")
            cursor.execute("""
                SELECT id, name, address, phone, practice_days
                FROM branches
                ORDER BY name
            """)
            assigned_branches = cursor.fetchall()
            
        else:
            # Regular coaches can only access assigned branches
            print("🔍 Regular coach - getting assigned branches only")
            cursor.execute("""
                SELECT 
                    b.id,
                    b.name,
                    b.address,
                    b.phone,
                    b.practice_days
                FROM coach_assignments ca
                JOIN branches b ON ca.branch_id = b.id
                WHERE ca.user_id = %s
                ORDER BY b.name
            """, (user["id"],))
            assigned_branches = cursor.fetchall()
            
        print(f"✅ Found {len(assigned_branches)} assigned branches")
        for branch in assigned_branches:
            print(f"   - {branch['name']} (ID: {branch['id']})")
            
        # Get current branch from user profile
        cursor.execute("""
            SELECT b.id, b.name, b.address, b.phone, b.practice_days
            FROM users u
            LEFT JOIN branches b ON u.branch_id = b.id
            WHERE u.id = %s
        """, (user["id"],))
        current_branch_result = cursor.fetchone()

        # Format current branch
        current_branch = None
        if current_branch_result and current_branch_result['id']:
            current_branch = {
                'id': current_branch_result['id'],
                'name': current_branch_result['name'],
                'address': current_branch_result['address'],
                'phone': current_branch_result['phone'],
                'practice_days': current_branch_result['practice_days']
            }
            print(f"✅ Current branch: {current_branch['name']} (ID: {current_branch['id']})")
        else:
            print("⚠️ No current branch set for user")

        return {
            "success": True,
            "assigned_branches": assigned_branches,
            "current_branch": current_branch,
            "total_branches": len(assigned_branches)
        }

    except Exception as e:
        print(f"❌ Error getting assigned branches: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get assigned branches: {str(e)}")
    finally:
        cursor.close()
        conn.close()

# ✅ NEW: Set active branch for coach
@router.post("/set-active-branch/{branch_id}")
def set_coach_active_branch(branch_id: int, user=Depends(get_current_user)):
    """Set the active branch for a coach"""
    if user["role"] not in ["coach", "head_coach"]:
        raise HTTPException(status_code=403, detail="Only coaches can set active branch")

    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        print(f"🔍 Setting active branch {branch_id} for {user['role']} {user['name']}")
        
        # Check if branch exists
        cursor.execute("SELECT id, name FROM branches WHERE id = %s", (branch_id,))
        branch = cursor.fetchone()
        if not branch:
            print(f"❌ Branch {branch_id} not found")
            raise HTTPException(status_code=404, detail="Branch not found")

        # For regular coaches, verify they are assigned to this branch
        if user["role"] == "coach":
            print(f"🔍 Verifying coach assignment to branch {branch_id}")
            cursor.execute("""
                SELECT id FROM coach_assignments 
                WHERE user_id = %s AND branch_id = %s
            """, (user["id"], branch_id))
            assignment = cursor.fetchone()
            
            if not assignment:
                print(f"❌ Coach {user['name']} not assigned to branch {branch_id}")
                raise HTTPException(
                    status_code=403, 
                    detail="You are not assigned to this branch"
                )
            print(f"✅ Coach assignment verified")
        else:
            print(f"✅ Head coach can access any branch")

        # Update user's current branch
        cursor.execute("""
            UPDATE users 
            SET branch_id = %s 
            WHERE id = %s
        """, (branch_id, user["id"]))

        conn.commit()
        print(f"✅ Active branch set to {branch['name']} for {user['name']}")

        return {
            "success": True,
            "message": f"Active branch set to {branch['name']}",
            "new_active_branch_id": branch_id,
            "new_active_branch_name": branch['name']
        }

    except HTTPException:
        conn.rollback()
        raise
    except Exception as e:
        conn.rollback()
        print(f"❌ Error setting active branch: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to set active branch: {str(e)}")
    finally:
        cursor.close()
        conn.close()