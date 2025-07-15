# Replace the entire payments.py file with this fixed version:

from fastapi import APIRouter, Depends, HTTPException
from app.database import get_connection
from app.deps import get_current_user
from app.utils.auth_utils import can_access_branch
from pydantic import BaseModel
from datetime import datetime

router = APIRouter()

class PaymentMark(BaseModel):
    athlete_id: int
    session_date: str
    status: str

@router.get("/summary/{branch_id}")
def get_payment_summary(branch_id: int, user=Depends(get_current_user)):
    can_access_branch(user, branch_id)
    conn = get_connection()
    cursor = conn.cursor(dictionary=True, buffered=True)

    cursor.execute("""
        SELECT a.id AS athlete_id, u.name AS athlete_name
        FROM athletes a
        JOIN users u ON a.user_id = u.id
        WHERE u.branch_id = %s AND u.role = 'athlete' AND u.approved = 1
        ORDER BY u.name
    """, (branch_id,))
    athletes = cursor.fetchall()

    cursor.execute("SELECT * FROM payments WHERE branch_id = %s", (branch_id,))
    payments = cursor.fetchall()

    session_dates = sorted({str(p["due_date"]) for p in payments})

    summary = []
    for athlete in athletes:
        athlete_id = athlete["athlete_id"]
        statuses = {date: "pending" for date in session_dates}
        for payment in payments:
            if payment["athlete_id"] == athlete_id:
                statuses[str(payment["due_date"])] = payment["status"]
        summary.append({
            "athlete_id": athlete_id,
            "athlete_name": athlete["athlete_name"],
            "statuses": statuses,
        })

    return {
        "records": summary,
        "session_dates": session_dates,
    }

@router.post("/mark")
def mark_payment(data: PaymentMark, user=Depends(get_current_user)):
    if user["role"] not in ["coach", "head_coach"]:
        raise HTTPException(status_code=403, detail="Only coaches can update payments")

    conn = get_connection()
    cursor = conn.cursor(dictionary=True, buffered=True)

    try:
        session_dt = datetime.strptime(data.session_date, "%Y-%m-%d").date()
        due_date = session_dt.replace(day=1)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD.")

    print(f"🔍 DEBUG - Marking payment:")
    print(f"   - athlete_id: {data.athlete_id}")
    print(f"   - session_date: {data.session_date}")
    print(f"   - session_dt: {session_dt}")
    print(f"   - due_date: {due_date}")
    print(f"   - status: {data.status}")
    print(f"   - branch_id: {user['branch_id']}")

    cursor.execute("SELECT * FROM athletes WHERE id = %s", (data.athlete_id,))
    athlete_check = cursor.fetchone()
    print(f"🔍 Athlete exists: {athlete_check is not None}")
    if athlete_check:
        print(f"   - Athlete details: {athlete_check}")

    cursor.execute("""
        SELECT * FROM payments 
        WHERE athlete_id = %s AND due_date = %s
    """, (data.athlete_id, due_date))
    existing_payment = cursor.fetchone()
    print(f"🔍 Existing payment: {existing_payment}")

    cursor.execute("""
        INSERT INTO payments (
            athlete_id, session_date, due_date, branch_id, status, confirmed_by_coach
        ) VALUES (%s, %s, %s, %s, %s, TRUE)
        ON DUPLICATE KEY UPDATE 
            status = VALUES(status),
            confirmed_by_coach = TRUE
    """, (
        data.athlete_id,
        session_dt,
        due_date,
        user["branch_id"],
        data.status,
    ))

    affected_rows = cursor.rowcount
    print(f"🔍 Affected rows: {affected_rows}")

    cursor.execute("""
        SELECT * FROM payments 
        WHERE athlete_id = %s AND due_date = %s
    """, (data.athlete_id, due_date))
    updated_payment = cursor.fetchone()
    print(f"🔍 Updated payment: {updated_payment}")

    conn.commit()
    return {
        "message": "Payment status updated",
        "debug": {
            "athlete_id": data.athlete_id,
            "due_date": str(due_date),
            "status": data.status,
            "affected_rows": affected_rows
        }
    }

# ✅ FIXED: Replaced the old endpoint with the enhanced debug version
# Replace the payment status endpoint in your payments.py with this fixed version:

@router.get("/{user_id}/status")
def get_athlete_payment_status_fixed(user_id: int, user=Depends(get_current_user)):
    """
    Get payment status for an athlete by user_id with detailed debugging.
    FIXED: Removed created_at column that doesn't exist in payments table.
    """
    conn = get_connection()
    cursor = conn.cursor(dictionary=True, buffered=True)

    try:
        print(f"🔍 PAYMENTS ROUTER DEBUG - Getting payment status for user_id: {user_id}")
        
        # First, convert user_id to athlete_id
        cursor.execute("""
            SELECT a.id as athlete_id, u.name, u.email, u.branch_id
            FROM athletes a
            JOIN users u ON a.user_id = u.id
            WHERE u.id = %s
        """, (user_id,))
        
        athlete_record = cursor.fetchone()
        print(f"🔍 PAYMENTS ROUTER DEBUG - Found athlete record: {athlete_record}")

        if not athlete_record:
            print(f"❌ PAYMENTS ROUTER DEBUG - No athlete record found for user_id: {user_id}")
            # Return empty status for current month instead of 404
            current_month = datetime.now().strftime("%Y-%m-01")
            return {current_month: "pending"}

        actual_athlete_id = athlete_record["athlete_id"]
        print(f"✅ PAYMENTS ROUTER DEBUG - Using athlete_id: {actual_athlete_id}")

        # ✅ FIXED: Removed 'created_at' from SELECT since it doesn't exist in payments table
        cursor.execute("""
            SELECT 
                id,
                athlete_id,
                session_date,
                due_date, 
                status, 
                confirmed_by_coach,
                branch_id
            FROM payments
            WHERE athlete_id = %s
            ORDER BY due_date DESC, id DESC
        """, (actual_athlete_id,))
        
        rows = cursor.fetchall()
        print(f"🔍 PAYMENTS ROUTER DEBUG - Found {len(rows)} payment records for athlete_id {actual_athlete_id}:")
        for i, row in enumerate(rows):
            print(f"   Record {i+1}: ID={row['id']}, due_date={row['due_date']}, status='{row['status']}', session_date={row['session_date']}")

        # Build result dictionary with due_date as key
        result = {}
        seen_due_dates = set()
        
        for row in rows:
            due_date_key = row["due_date"].strftime("%Y-%m-%d")
            
            # Only use the first (most recent) record for each due_date
            if due_date_key not in seen_due_dates:
                result[due_date_key] = row["status"]
                seen_due_dates.add(due_date_key)
                print(f"✅ PAYMENTS ROUTER DEBUG - Added to result: {due_date_key} = '{row['status']}'")
            else:
                print(f"⏭️  PAYMENTS ROUTER DEBUG - Skipping duplicate due_date: {due_date_key}")

        print(f"🔍 PAYMENTS ROUTER DEBUG - Final payment result before return: {result}")
        
        # If no payments found, return pending for current month
        if not result:
            current_month = datetime.now().strftime("%Y-%m-01")
            result[current_month] = "pending"
            print(f"🔍 PAYMENTS ROUTER DEBUG - No payments found, returning pending for {current_month}")

        return result

    except Exception as e:
        print(f"❌ PAYMENTS ROUTER DEBUG - Error getting payment status: {e}")
        import traceback
        print(f"❌ PAYMENTS ROUTER DEBUG - Full traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Failed to get payment status: {str(e)}")
    finally:
        cursor.close()
        conn.close()