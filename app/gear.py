from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from app.database import get_connection
from app.deps import get_current_user

router = APIRouter()

class GearPost(BaseModel):
    content: str

def get_assigned_branch_id(user: dict) -> int:
    if user["role"] in ["coach", "head_coach"]:
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT branch_id FROM coach_assignments WHERE user_id = %s LIMIT 1", (user["id"],))
        assignment = cursor.fetchone()
        cursor.close()
        conn.close()
        if assignment:
            return assignment["branch_id"]
    elif user["role"] == "athlete":
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT u.branch_id FROM athletes a
            JOIN users u ON a.user_id = u.id
            WHERE u.id = %s
            LIMIT 1
        """, (user["id"],))
        result = cursor.fetchone()
        cursor.close()
        conn.close()
        if result and result.get("branch_id"):
            return result["branch_id"]
    
    # fallback
    return user.get("branch_id")

@router.get("/{branch_id}")
def get_gear(branch_id: int, user=Depends(get_current_user)):
    assigned_branch = get_assigned_branch_id(user)
    print(f"User {user['id']} role {user['role']} assigned_branch={assigned_branch} requested branch_id={branch_id}")
    
    if user["role"] not in ["coach", "head_coach", "athlete"]:
        raise HTTPException(status_code=403, detail="Not authorized to view gear")
    
    # ✅ UPDATED: Head coaches can view gear for any branch
    if user["role"] == "head_coach":
        # Head coaches can view gear for any branch
        print(f"Head coach {user['id']} accessing gear for branch {branch_id}")
    else:
        # Regular coaches and athletes can only view their assigned branch
        if assigned_branch != branch_id:
            print(f"Access denied: assigned branch {assigned_branch} != requested {branch_id}")
            raise HTTPException(status_code=403, detail="You can only view gear for your assigned branch")
    
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT * FROM posts
        WHERE thread_id IN (
            SELECT id FROM threads WHERE branch_id = %s AND title = 'gear'
        )
        ORDER BY created_at DESC LIMIT 1
    """, (branch_id,))
    post = cursor.fetchone()
    cursor.close()
    conn.close()
    
    print(f"Returning gear post: {post}")
    return post or {"message": "No gear updates posted yet"}

@router.post("/{branch_id}")
async def post_gear(branch_id: int, data: GearPost, user=Depends(get_current_user)):
    if user["role"] not in ["coach", "head_coach"]:
        raise HTTPException(status_code=403, detail="Only coaches can post gear")
    
    # Head coaches can post gear to any branch - NO BRANCH CHECK
    if user["role"] == "head_coach":
        print(f"✅ Head coach {user['id']} posting gear to branch {branch_id} - ALLOWED")
    else:
        # ONLY check branch assignment for regular coaches
        assigned_branch = get_assigned_branch_id(user)
        print(f"🔄 Regular coach {user['id']} assigned_branch={assigned_branch} posting to branch {branch_id}")
        if assigned_branch != branch_id:
            raise HTTPException(status_code=403, detail="You can only post gear for your assigned branch")
    
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    
    try:
        # Get or create gear thread for the branch
        cursor.execute("SELECT id FROM threads WHERE branch_id = %s AND title = 'gear'", (branch_id,))
        thread = cursor.fetchone()
        
        if not thread:
            cursor.execute("INSERT INTO threads (branch_id, title) VALUES (%s, %s)", (branch_id, "gear"))
            conn.commit()
            thread_id = cursor.lastrowid
        else:
            thread_id = thread["id"]
        
        # Clear buffer if necessary
        cursor.fetchall()
        
        # Insert the gear post
        cursor.execute(
            "INSERT INTO posts (thread_id, user_id, message) VALUES (%s, %s, %s)",
            (thread_id, user["id"], data.content)
        )
        conn.commit()
        
        # ✅ NEW: Send notification to branch users
        try:
            from app.services.notification_service import NotificationService
            await NotificationService.send_gear_notification(
                branch_id=branch_id,
                sender_id=user["id"]
            )
        except Exception as e:
            # Don't fail the post if notification fails
            print(f"Gear notification error: {e}")
        
        print(f"✅ Successfully posted gear to branch {branch_id} by user {user['id']} ({user['role']})")
        return {"message": "Gear update posted successfully"}
        
    except Exception as e:
        print(f"❌ Error posting gear: {e}")
        conn.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to post gear: {str(e)}")
    finally:
        cursor.close()
        conn.close()

# ✅ NEW ENDPOINT: Get all branches for head coaches
@router.get("/branches/all")
def get_all_branches_for_gear(user=Depends(get_current_user)):
    """
    Get all branches - only head coaches can access this.
    Used for branch selection in gear management.
    """
    if user["role"] != "head_coach":
        raise HTTPException(status_code=403, detail="Only head coaches can view all branches")
    
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    
    try:
        cursor.execute("""
            SELECT id, name, address, phone 
            FROM branches 
            ORDER BY name
        """)
        branches = cursor.fetchall()
        
        print(f"✅ Retrieved {len(branches)} branches for head coach {user['id']}")
        return {"success": True, "branches": branches}
        
    except Exception as e:
        print(f"❌ Error getting branches: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch branches: {str(e)}")
    finally:
        cursor.close()
        conn.close()