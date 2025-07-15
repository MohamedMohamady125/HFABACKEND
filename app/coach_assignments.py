# app/coach_assignments.py

from fastapi import APIRouter, Depends, HTTPException
from app.database import get_connection
from app.deps import get_current_user
from pydantic import BaseModel

router = APIRouter()

class CoachAssignment(BaseModel):
    branch_id: int

# =================== GET ALL COACHES ===================
@router.get("/all")
def get_all_coaches(user=Depends(get_current_user)):
    """Get all coaches in the system with their assignments"""
    if user["role"] != "head_coach":
        raise HTTPException(status_code=403, detail="Only head coaches can view all coaches")

    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        # Only get regular coaches, not head coaches
        cursor.execute("""
            SELECT 
                u.id,
                u.name,
                u.email,
                u.phone,
                u.role
            FROM users u
            WHERE u.role = 'coach'
            ORDER BY u.name
        """)
        coaches = cursor.fetchall()

        # Get assignments for each coach
        for coach in coaches:
            cursor.execute("""
                SELECT 
                    ca.branch_id,
                    b.name as branch_name,
                    b.address,
                    b.phone as branch_phone
                FROM coach_assignments ca
                JOIN branches b ON ca.branch_id = b.id
                WHERE ca.user_id = %s
            """, (coach['id'],))
            coach['assignments'] = cursor.fetchall()

        return coaches

    finally:
        cursor.close()
        conn.close()

# =================== GET COACH ASSIGNMENTS ===================
@router.get("/{coach_id}/assignments")
def get_coach_assignments(coach_id: int, user=Depends(get_current_user)):
    """Get assignments for a specific coach"""
    if user["role"] != "head_coach":
        raise HTTPException(status_code=403, detail="Only head coaches can view assignments")

    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        cursor.execute("""
            SELECT 
                ca.branch_id as id,
                b.name,
                b.address,
                b.phone,
                b.practice_days
            FROM coach_assignments ca
            JOIN branches b ON ca.branch_id = b.id
            WHERE ca.user_id = %s
        """, (coach_id,))
        assignments = cursor.fetchall()

        return assignments

    finally:
        cursor.close()
        conn.close()

# =================== ASSIGN COACH TO BRANCH ===================
@router.post("/{coach_id}/assign")
def assign_coach_to_branch(coach_id: int, assignment: CoachAssignment, user=Depends(get_current_user)):
    """Assign a coach to a branch"""
    if user["role"] != "head_coach":
        raise HTTPException(status_code=403, detail="Only head coaches can assign coaches")

    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        # Check if coach exists
        cursor.execute("SELECT id, name FROM users WHERE id = %s AND role IN ('coach', 'head_coach')", (coach_id,))
        coach = cursor.fetchone()
        if not coach:
            raise HTTPException(status_code=404, detail="Coach not found")

        # Check if branch exists
        cursor.execute("SELECT id, name FROM branches WHERE id = %s", (assignment.branch_id,))
        branch = cursor.fetchone()
        if not branch:
            raise HTTPException(status_code=404, detail="Branch not found")

        # Check if assignment already exists
        cursor.execute("""
            SELECT id FROM coach_assignments 
            WHERE user_id = %s AND branch_id = %s
        """, (coach_id, assignment.branch_id))
        existing = cursor.fetchone()
        
        if existing:
            return {"message": f"Coach {coach['name']} is already assigned to {branch['name']}"}

        # Create assignment
        cursor.execute("""
            INSERT INTO coach_assignments (user_id, branch_id, assigned_by, assigned_at)
            VALUES (%s, %s, %s, NOW())
        """, (coach_id, assignment.branch_id, user["id"]))

        conn.commit()

        return {"message": f"Coach {coach['name']} assigned to {branch['name']} successfully"}

    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=f"Assignment failed: {str(e)}")
    finally:
        cursor.close()
        conn.close()

# =================== UNASSIGN COACH FROM BRANCH ===================
@router.delete("/{coach_id}/unassign")
def unassign_coach_from_branch(coach_id: int, assignment: CoachAssignment, user=Depends(get_current_user)):
    """Remove a coach assignment from a branch"""
    if user["role"] != "head_coach":
        raise HTTPException(status_code=403, detail="Only head coaches can unassign coaches")

    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        # Check if assignment exists
        cursor.execute("""
            SELECT ca.id, u.name as coach_name, b.name as branch_name
            FROM coach_assignments ca
            JOIN users u ON ca.user_id = u.id
            JOIN branches b ON ca.branch_id = b.id
            WHERE ca.user_id = %s AND ca.branch_id = %s
        """, (coach_id, assignment.branch_id))
        
        existing = cursor.fetchone()
        if not existing:
            raise HTTPException(status_code=404, detail="Assignment not found")

        # Remove assignment
        cursor.execute("""
            DELETE FROM coach_assignments 
            WHERE user_id = %s AND branch_id = %s
        """, (coach_id, assignment.branch_id))

        conn.commit()

        return {"message": f"Coach {existing['coach_name']} unassigned from {existing['branch_name']} successfully"}

    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=f"Unassignment failed: {str(e)}")
    finally:
        cursor.close()
        conn.close()

# =================== GET ASSIGNMENT STATS ===================
# =================== GET ASSIGNMENT STATS ===================
@router.get("/assignment-stats")
def get_assignment_stats(user=Depends(get_current_user)):
    """Get assignment statistics"""
    if user["role"] != "head_coach":
        raise HTTPException(status_code=403, detail="Only head coaches can view stats")

    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        # Only count coaches, not head coaches
        cursor.execute("SELECT COUNT(*) as total FROM users WHERE role = 'coach'")
        total_coaches = cursor.fetchone()['total']

        # Assigned coaches
        cursor.execute("""
            SELECT COUNT(DISTINCT user_id) as assigned 
            FROM coach_assignments
            WHERE user_id IN (SELECT id FROM users WHERE role = 'coach')
        """)
        assigned_coaches = cursor.fetchone()['assigned']

        # Multi-branch coaches
        cursor.execute("""
            SELECT COUNT(*) as multi_branch
            FROM (
                SELECT user_id
                FROM coach_assignments
                WHERE user_id IN (SELECT id FROM users WHERE role = 'coach')
                GROUP BY user_id
                HAVING COUNT(*) > 1
            ) as multi
        """)
        multi_branch_coaches = cursor.fetchone()['multi_branch']

        return {
            "total_coaches": total_coaches,
            "assigned_coaches": assigned_coaches,
            "unassigned_coaches": total_coaches - assigned_coaches,
            "multi_branch_coaches": multi_branch_coaches
        }

    finally:
        cursor.close()
        conn.close()