from fastapi import HTTPException

def can_access_branch(user, branch_id: int):
    if user["role"] == "head_coach":
        # Head coach has access to all branches
        return
    if user["role"] == "coach" and user.get("branch_id") == branch_id:
        return
    raise HTTPException(status_code=403, detail="Access denied for this branch.")