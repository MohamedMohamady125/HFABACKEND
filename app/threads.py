from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from app.database import get_connection
from app.deps import get_current_user
from app.utils.auth_utils import can_access_branch

router = APIRouter()

class ThreadCreate(BaseModel):
    title: str

class MessageCreate(BaseModel):
    message: str

@router.get("/branch/{branch_id}")
def get_branch_threads(branch_id: int):
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        cursor.execute("""
            SELECT * FROM threads 
            WHERE branch_id = %s AND title != 'gear' 
            ORDER BY created_at ASC
        """, (branch_id,))
        threads = cursor.fetchall()

        if not threads:
            # Fetch branch name
            cursor.execute("SELECT name FROM branches WHERE id = %s", (branch_id,))
            branch = cursor.fetchone()
            branch_name = branch["name"] if branch else f"Branch {branch_id}"

            # Insert default thread with branch name
            cursor.execute("""
                INSERT INTO threads (branch_id, title, created_at) 
                VALUES (%s, %s, NOW())
            """, (branch_id, f"Branch: {branch_name} General"))
            conn.commit()

            # Re-fetch threads after insert
            cursor.execute("""
                SELECT * FROM threads 
                WHERE branch_id = %s AND title != 'gear' 
                ORDER BY created_at ASC
            """, (branch_id,))
            threads = cursor.fetchall()

        return threads

    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
    finally:
        cursor.close()
        conn.close()

@router.post("/branch/{branch_id}/ensure-thread")
def ensure_branch_thread(branch_id: int, user=Depends(get_current_user)):
    can_access_branch(user, branch_id)

    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        cursor.execute("""
            SELECT id FROM threads 
            WHERE branch_id = %s AND title != 'gear' 
            LIMIT 1
        """, (branch_id,))
        existing = cursor.fetchone()

        if not existing:
            # Fetch branch name
            cursor.execute("SELECT name FROM branches WHERE id = %s", (branch_id,))
            branch = cursor.fetchone()
            branch_name = branch["name"] if branch else f"Branch {branch_id}"

            cursor.execute("""
                INSERT INTO threads (branch_id, title, created_at) 
                VALUES (%s, %s, NOW())
            """, (branch_id, f"Branch: {branch_name} General"))
            conn.commit()
            thread_id = cursor.lastrowid
        else:
            thread_id = existing["id"]

        return {"thread_id": thread_id, "message": "Thread ready"}

    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
    finally:
        cursor.close()
        conn.close()

@router.get("/{thread_id}/posts")
def get_posts(thread_id: int):
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    
    try:
        cursor.execute("""
            SELECT p.id, p.message, p.user_id, u.name AS author, p.created_at
            FROM posts p
            JOIN users u ON p.user_id = u.id
            WHERE p.thread_id = %s
            ORDER BY p.created_at ASC
        """, (thread_id,))
        posts = cursor.fetchall()
        return posts
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
    finally:
        cursor.close()
        conn.close()

@router.post("/branch/{branch_id}/create")
def create_thread(branch_id: int, data: ThreadCreate, user=Depends(get_current_user)):
    can_access_branch(user, branch_id)

    conn = get_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
            INSERT INTO threads (branch_id, title, created_at) 
            VALUES (%s, %s, NOW())
        """, (branch_id, data.title))
        conn.commit()
        
        # Return the created thread ID
        thread_id = cursor.lastrowid
        return {"message": "Thread created", "thread_id": thread_id}
        
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to create thread: {str(e)}")
    finally:
        cursor.close()
        conn.close()

@router.post("/{thread_id}/post")
async def post_message(thread_id: int, data: MessageCreate, user=Depends(get_current_user)):
    if user["role"] not in ["coach", "head_coach"]:
        raise HTTPException(status_code=403, detail="Only coaches can post to threads")

    conn = get_connection()
    cursor = conn.cursor()
    
    try:
        # Verify thread exists and get branch_id for additional security
        cursor.execute("SELECT branch_id FROM threads WHERE id = %s", (thread_id,))
        thread = cursor.fetchone()
        
        if not thread:
            raise HTTPException(status_code=404, detail="Thread not found")
        
        cursor.execute("""
            INSERT INTO posts (thread_id, user_id, message, created_at) 
            VALUES (%s, %s, %s, NOW())
        """, (thread_id, user["id"], data.message))
        conn.commit()
        
        # ✅ NEW: Send notification to branch users
        try:
            from app.services.notification_service import NotificationService
            await NotificationService.send_thread_notification(
                thread_id=thread_id,
                sender_id=user["id"],
                message_preview=data.message
            )
        except Exception as e:
            # Don't fail the post if notification fails
            print(f"Notification error: {e}")
        
        return {"message": "Post added", "success": True}
        
    except HTTPException:
        raise
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to post message: {str(e)}")
    finally:
        cursor.close()
        conn.close()


# ✅ NEW ENDPOINT: Delete all head coach messages in a branch
@router.delete("/branch/{branch_id}/delete-head-coach-messages")
def delete_all_head_coach_messages(branch_id: int, user=Depends(get_current_user)):
    """
    Delete all messages sent by head coaches in threads for a specific branch.
    Only head coaches can perform this action.
    """
    # Check if user is head coach
    if user["role"] != "head_coach":
        raise HTTPException(
            status_code=403,
            detail="Only head coaches can delete messages"
        )
    
    # Verify user can access this branch
    can_access_branch(user, branch_id)
    
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    
    try:
        # First, get all thread IDs for this branch
        cursor.execute("""
            SELECT id FROM threads 
            WHERE branch_id = %s
        """, (branch_id,))
        threads = cursor.fetchall()
        
        if not threads:
            return {
                "success": True,
                "message": "No threads found for this branch",
                "deleted_count": 0
            }
        
        thread_ids = [thread["id"] for thread in threads]
        
        # Count messages by head coaches in these threads before deletion
        placeholders = ','.join(['%s'] * len(thread_ids))
        cursor.execute(f"""
            SELECT COUNT(*) as count
            FROM posts p
            JOIN users u ON p.user_id = u.id
            WHERE p.thread_id IN ({placeholders}) 
            AND u.role = 'head_coach'
        """, thread_ids)
        
        count_result = cursor.fetchone()
        deleted_count = count_result["count"] if count_result else 0
        
        # Delete all messages by head coaches in these threads
        if deleted_count > 0:
            cursor.execute(f"""
                DELETE p FROM posts p
                JOIN users u ON p.user_id = u.id
                WHERE p.thread_id IN ({placeholders}) 
                AND u.role = 'head_coach'
            """, thread_ids)
        
        conn.commit()
        
        return {
            "success": True,
            "message": f"Successfully deleted {deleted_count} head coach messages",
            "deleted_count": deleted_count
        }
        
    except HTTPException:
        raise
    except Exception as e:
        conn.rollback()
        print(f"Error deleting head coach messages: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to delete messages: {str(e)}"
        )
    finally:
        cursor.close()
        conn.close()