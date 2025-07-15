from fastapi import APIRouter, Depends, HTTPException
from app.database import get_connection
from app.deps import get_current_user
from passlib.hash import bcrypt

router = APIRouter()

@router.get("/branches")
def list_all_branches_for_head_coach(user=Depends(get_current_user)):
    if user["role"] != "head_coach":
        raise HTTPException(status_code=403, detail="Access denied")

    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT id, name, address, phone FROM branches ORDER BY name")
    branches = cursor.fetchall()
    cursor.close()
    conn.close()
    return branches

@router.post("/select-branch/{branch_id}")
def select_branch_for_head_coach(branch_id: int, user=Depends(get_current_user)):
    if user["role"] != "head_coach":
        raise HTTPException(status_code=403, detail="Access denied")

    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    # Verify branch exists
    cursor.execute("SELECT id FROM branches WHERE id = %s", (branch_id,))
    branch = cursor.fetchone()
    if not branch:
        raise HTTPException(status_code=404, detail="Branch not found")

    # Update user's branch_id temporarily for session (or implement as needed)
    cursor.execute("UPDATE users SET branch_id = %s WHERE id = %s", (branch_id, user["id"]))
    conn.commit()

    cursor.close()
    conn.close()

    return {"message": f"Branch {branch_id} selected"}