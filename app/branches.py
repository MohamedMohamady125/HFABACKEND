# app/branches.py - Fixed with correct route order

from fastapi import APIRouter, Depends, HTTPException
from app.database import get_connection
from app.deps import get_current_user

router = APIRouter()

# =================== PUBLIC ROUTES (NO AUTH REQUIRED) ===================
# These MUST come before parameterized routes like /{branch_id}

@router.get("/public")
def get_public_branches():
    """
    Get all branches for public use (registration form).
    No authentication required.
    """
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    
    try:
        cursor.execute("""
            SELECT id, name, address, phone, practice_days
            FROM branches
            ORDER BY name
        """)
        branches = cursor.fetchall()
        
        print(f"✅ Retrieved {len(branches)} branches for public access")
        return branches
        
    except Exception as e:
        print(f"❌ Error getting public branches: {e}")
        raise HTTPException(
            status_code=500, 
            detail="Failed to load branches"
        )
    finally:
        cursor.close()
        conn.close()

@router.get("/")
def list_branches():
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT id, name, address, phone, video_url, practice_days 
        FROM branches
        ORDER BY name
    """)
    branches = cursor.fetchall()
    cursor.close()
    conn.close()
    return branches

# =================== AUTHENTICATED ROUTES ===================

@router.get("/all")
def get_all_branches(user=Depends(get_current_user)):
    """Get all branches for assignment purposes"""
    if user["role"] != "head_coach":
        raise HTTPException(status_code=403, detail="Only head coaches can view all branches")
    
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT id, name, address, phone, practice_days
        FROM branches
        ORDER BY name
    """)
    branches = cursor.fetchall()
    cursor.close()
    conn.close()
    return branches

# =================== PARAMETERIZED ROUTES (MUST BE LAST) ===================
# These routes with path parameters should come AFTER specific routes

@router.get("/{branch_id}")
def get_branch(branch_id: int):
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM branches WHERE id = %s", (branch_id,))
    branch = cursor.fetchone()
    cursor.close()
    conn.close()
    if not branch:
        raise HTTPException(status_code=404, detail="Branch not found")
    return branch

# =================== BRANCH SELECTION FOR HEAD COACH ===================

@router.post("/select-branch/{branch_id}")
def select_branch_for_head_coach(branch_id: int, user=Depends(get_current_user)):
    if user["role"] != "head_coach":
        raise HTTPException(status_code=403, detail="Access denied")

    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        # Verify branch exists
        cursor.execute("SELECT id, name FROM branches WHERE id = %s", (branch_id,))
        branch = cursor.fetchone()
        if not branch:
            raise HTTPException(status_code=404, detail="Branch not found")

        # Update user's branch_id for session context
        cursor.execute("UPDATE users SET branch_id = %s WHERE id = %s", (branch_id, user["id"]))
        conn.commit()

        return {"message": f"Successfully switched to {branch['name']}"}

    finally:
        cursor.close()
        conn.close()

@router.get("/coach/assigned-branches")
def get_coach_assigned_branches(user=Depends(get_current_user)):
    """
    Get all branches a coach is assigned to.
    A coach can only view their own assigned branches.
    """
    if user["role"] != "coach":
        raise HTTPException(status_code=403, detail="Only coaches can access this resource.")

    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        cursor.execute("""
            SELECT
                b.id AS branch_id,
                b.name AS branch_name,
                b.address,
                b.phone
            FROM coach_assignments ca
            JOIN branches b ON ca.branch_id = b.id
            WHERE ca.user_id = %s
            ORDER BY b.name
        """, (user["id"],)) # Use user["id"] from get_current_user
        assigned_branches = cursor.fetchall()

        # Additionally, get the currently active branch for the coach
        cursor.execute("""
            SELECT
                b.id AS current_branch_id,
                b.name AS current_branch_name
            FROM users u
            JOIN branches b ON u.branch_id = b.id
            WHERE u.id = %s
        """, (user["id"],))
        current_active_branch = cursor.fetchone()

        return {
            "assigned_branches": assigned_branches,
            "current_active_branch": current_active_branch
        }

    finally:
        cursor.close()
        conn.close()

# =================== SET A COACH'S ACTIVE BRANCH ===================

@router.post("/coach/set-active-branch/{branch_id}")
def set_coach_active_branch(branch_id: int, user=Depends(get_current_user)):
    """
    Set the active branch for the logged-in coach.
    The coach must be assigned to the branch they are trying to set as active.
    """
    if user["role"] != "coach":
        raise HTTPException(status_code=403, detail="Only coaches can set their active branch.")

    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        # 1. Verify the branch_id exists and the coach is assigned to it
        cursor.execute("""
            SELECT ca.branch_id
            FROM coach_assignments ca
            WHERE ca.user_id = %s AND ca.branch_id = %s
        """, (user["id"], branch_id))
        is_assigned = cursor.fetchone()

        if not is_assigned:
            raise HTTPException(status_code=403, detail="You are not assigned to this branch.")

        # 2. Update the user's active branch_id in the 'users' table
        cursor.execute("""
            UPDATE users
            SET branch_id = %s
            WHERE id = %s
        """, (branch_id, user["id"]))
        conn.commit()

        # 3. Fetch the updated branch name to return
        cursor.execute("SELECT name FROM branches WHERE id = %s", (branch_id,))
        updated_branch_info = cursor.fetchone()

        return {
            "message": f"Active branch set to {updated_branch_info['name']} successfully.",
            "new_active_branch_id": branch_id,
            "new_active_branch_name": updated_branch_info['name']
        }

    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to set active branch: {str(e)}")
    finally:
        cursor.close()
        conn.close()