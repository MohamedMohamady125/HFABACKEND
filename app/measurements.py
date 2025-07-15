from fastapi import APIRouter, Depends, HTTPException
from app.database import get_connection
from app.deps import get_current_user

router = APIRouter()

@router.post("/measurements")  # ✅ No /athlete prefix
def save_measurements(data: dict, user=Depends(get_current_user)):
    """Save athlete measurements - accepts any dict with measurement fields"""
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        cursor.execute("SELECT id FROM athletes WHERE user_id = %s", (user["id"],))
        athlete = cursor.fetchone()
        if not athlete:
            raise HTTPException(status_code=404, detail="Athlete not found")

        # Extract measurements, defaulting to None if not provided
        height = data.get('height')
        weight = data.get('weight')
        arm = data.get('arm')
        leg = data.get('leg')
        fat = data.get('fat')
        muscle = data.get('muscle')

        # Convert string values to float, keep None as None
        def safe_float(value):
            if value is None or value == "":
                return None
            try:
                return float(value)
            except (ValueError, TypeError):
                return None

        height = safe_float(height)
        weight = safe_float(weight)
        arm = safe_float(arm)
        leg = safe_float(leg)
        fat = safe_float(fat)
        muscle = safe_float(muscle)

        # Check if any valid measurement data is provided
        if all(val is None for val in [height, weight, arm, leg, fat, muscle]):
            raise HTTPException(status_code=400, detail="No valid measurement data provided")

        print(f"💾 Saving measurements for athlete {athlete['id']}: height={height}, weight={weight}, arm={arm}, leg={leg}, fat={fat}, muscle={muscle}")

        cursor.execute("""
            INSERT INTO measurement_logs (athlete_id, height, weight, arm, leg, fat, muscle)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (athlete["id"], height, weight, arm, leg, fat, muscle))

        conn.commit()
        
        print(f"✅ Measurements saved successfully for athlete {athlete['id']}")
        return {"message": "Measurements saved successfully!", "success": True}

    except HTTPException as e:
        raise e
    except Exception as e:
        print("❌ DB Insert Error:", e)
        raise HTTPException(status_code=500, detail=f"Failed to save measurements: {e}")
    finally:
        cursor.close()
        conn.close()

@router.get("/measurements")  # ✅ No /athlete prefix
def get_latest_measurements(user=Depends(get_current_user)):
    """Get latest athlete measurements"""
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        cursor.execute("SELECT id FROM athletes WHERE user_id = %s", (user["id"],))
        athlete = cursor.fetchone()
        if not athlete:
            raise HTTPException(status_code=404, detail="Athlete not found")

        cursor.execute("""
            SELECT height, weight, arm, leg, fat, muscle
            FROM measurement_logs
            WHERE athlete_id = %s
            ORDER BY id DESC
            LIMIT 1
        """, (athlete["id"],))

        data = cursor.fetchone()
        
        if not data:
            print(f"ℹ️ No measurements found for athlete {athlete['id']}")
            return {
                'success': True,
                'data': {
                    'height': None, 'weight': None, 'arm': None,
                    'leg': None, 'fat': None, 'muscle': None
                }
            }

        print(f"✅ Retrieved measurements for athlete {athlete['id']}: {data}")
        return {'success': True, 'data': data}

    except Exception as e:
        print("❌ DB Query Error:", e)
        raise HTTPException(status_code=500, detail=f"Failed to fetch measurements: {e}")
    finally:
        cursor.close()
        conn.close()