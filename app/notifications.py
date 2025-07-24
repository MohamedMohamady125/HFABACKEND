import os
from dotenv import load_dotenv
from fastapi import HTTPException, APIRouter, Depends
from pywebpush import webpush, WebPushException
from app.database import get_connection
from app.deps import get_current_user
from app.schemas import PushSubscription

# 🔐 Load environment variables from .env (commented out for Railway)
# load_dotenv()  # This might interfere with Railway environment variables

# 🔑 Grab VAPID keys from environment
VAPID_PRIVATE_KEY = os.getenv("VAPID_PRIVATE_KEY")
VAPID_PUBLIC_KEY = os.getenv("VAPID_PUBLIC_KEY")
VAPID_CLAIMS = {
    "sub": os.getenv("VAPID_EMAIL")
}

# ✅ DEBUG LOGGING - See what Railway provides
print(f"🔧 Debug VAPID_PRIVATE_KEY: {VAPID_PRIVATE_KEY[:20] if VAPID_PRIVATE_KEY else 'None'}...")
print(f"🔧 Debug VAPID_PUBLIC_KEY: {VAPID_PUBLIC_KEY[:20] if VAPID_PUBLIC_KEY else 'None'}...")
print(f"🔧 Debug VAPID_EMAIL: {os.getenv('VAPID_EMAIL')}")
print(f"🔧 Environment has {len(os.environ)} variables")

router = APIRouter()

@router.post("/webpush/subscribe")
async def subscribe_to_web_push(
    subscription: PushSubscription,
    user=Depends(get_current_user)
):
    print("📦 New Web Push Subscription Received:")
    print(f"   User: {user.get('name', 'Unknown')} (ID: {user.get('id')})")
    print(f"   Endpoint: {subscription.endpoint}")
    print(f"   Keys: p256dh={subscription.keys.p256dh[:20]}..., auth={subscription.keys.auth[:20]}...")

    endpoint = subscription.endpoint
    p256dh = subscription.keys.p256dh
    auth_key = subscription.keys.auth

    if not endpoint or not p256dh or not auth_key:
        print("❌ Incomplete subscription info")
        raise HTTPException(status_code=400, detail="Incomplete subscription info")

    # ✅ Enhanced VAPID validation with better logging
    print(f"🔧 Checking VAPID keys - Private: {bool(VAPID_PRIVATE_KEY)}, Public: {bool(VAPID_PUBLIC_KEY)}")
    if not VAPID_PRIVATE_KEY or not VAPID_PUBLIC_KEY:
        print("❌ VAPID keys not configured")
        print(f"❌ VAPID_PRIVATE_KEY exists: {bool(VAPID_PRIVATE_KEY)}")
        print(f"❌ VAPID_PUBLIC_KEY exists: {bool(VAPID_PUBLIC_KEY)}")
        raise HTTPException(status_code=500, detail="Server push configuration error")

    conn = get_connection()
    cursor = conn.cursor()

    try:
        # 🔄 Check if this user already has a subscription with this endpoint
        cursor.execute("""
            SELECT id FROM webpush_subscriptions 
            WHERE user_id = %s AND endpoint = %s
        """, (user["id"], endpoint))
        existing = cursor.fetchone()

        if existing:
            print("ℹ️ Subscription already exists, updating keys")
            cursor.execute("""
                UPDATE webpush_subscriptions
                SET p256dh = %s, auth = %s
                WHERE user_id = %s AND endpoint = %s
            """, (p256dh, auth_key, user["id"], endpoint))
        else:
            print("✅ New subscription, saving to DB")
            cursor.execute("""
                INSERT INTO webpush_subscriptions (user_id, endpoint, p256dh, auth)
                VALUES (%s, %s, %s, %s)
            """, (user["id"], endpoint, p256dh, auth_key))

        conn.commit()
        print("✅ Subscription saved to database")

        # 🔔 Send test push notification (only if VAPID keys are properly configured)
        if VAPID_PRIVATE_KEY and VAPID_PUBLIC_KEY and len(VAPID_PRIVATE_KEY) > 20:
            try:
                # ✅ Prepare subscription info in correct format for pywebpush
                subscription_info = {
                    "endpoint": endpoint,
                    "keys": {
                        "p256dh": p256dh,
                        "auth": auth_key
                    }
                }
                
                print("🔔 Sending test push notification...")
                webpush(
                    subscription_info=subscription_info,
                    data="🎉 You are now subscribed to HFA notifications!",
                    vapid_private_key=VAPID_PRIVATE_KEY,
                    vapid_claims=VAPID_CLAIMS
                )
                print("✅ Test push notification sent successfully")
                return {"message": "Subscribed and test push sent!"}

            except WebPushException as push_ex:
                print(f"⚠️ Push notification failed (but subscription saved): {push_ex}")
                return {"message": "Subscribed successfully (test push failed)", "push_error": str(push_ex)}
        else:
            print("⚠️ VAPID keys not configured properly, skipping test push")
            print(f"⚠️ VAPID_PRIVATE_KEY length: {len(VAPID_PRIVATE_KEY) if VAPID_PRIVATE_KEY else 0}")
            print(f"⚠️ VAPID_PUBLIC_KEY length: {len(VAPID_PUBLIC_KEY) if VAPID_PUBLIC_KEY else 0}")
            return {"message": "Subscribed successfully (VAPID keys not configured for push testing)"}

    except Exception as e:
        print(f"❌ Error saving subscription: {e}")
        conn.rollback()
        raise HTTPException(status_code=500, detail=f"Subscription failed: {str(e)}")
    finally:
        cursor.close()
        conn.close()

# ✅ Additional endpoint to test sending push to all users
@router.post("/webpush/send-to-all")
async def send_push_to_all(
    message: str,
    user=Depends(get_current_user)
):
    """Send push notification to all subscribed users"""
    if user.get("role") not in ["admin", "head_coach"]:
        raise HTTPException(status_code=403, detail="Not authorized to send push notifications")
    
    conn = get_connection()
    cursor = conn.cursor()
    
    try:
        # Get all active subscriptions
        cursor.execute("""
            SELECT user_id, endpoint, p256dh, auth 
            FROM webpush_subscriptions
        """)
        subscriptions = cursor.fetchall()
        
        sent_count = 0
        failed_count = 0
        
        for sub in subscriptions:
            try:
                subscription_info = {
                    "endpoint": sub[1],
                    "keys": {
                        "p256dh": sub[2],
                        "auth": sub[3]
                    }
                }
                
                webpush(
                    subscription_info=subscription_info,
                    data=message,
                    vapid_private_key=VAPID_PRIVATE_KEY,
                    vapid_claims=VAPID_CLAIMS
                )
                sent_count += 1
                
            except WebPushException as e:
                print(f"Failed to send to user {sub[0]}: {e}")
                failed_count += 1
        
        return {
            "message": f"Push sent to {sent_count} users, {failed_count} failed",
            "sent": sent_count,
            "failed": failed_count
        }
        
    except Exception as e:
        print(f"❌ Error sending bulk push: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        cursor.close()
        conn.close()

# ✅ Debug endpoint to check environment variables
@router.get("/webpush/debug-env")
async def debug_environment():
    """Debug endpoint to check environment variables"""
    return {
        "vapid_private_exists": bool(VAPID_PRIVATE_KEY),
        "vapid_private_length": len(VAPID_PRIVATE_KEY) if VAPID_PRIVATE_KEY else 0,
        "vapid_public_exists": bool(VAPID_PUBLIC_KEY),
        "vapid_public_length": len(VAPID_PUBLIC_KEY) if VAPID_PUBLIC_KEY else 0,
        "vapid_email": os.getenv("VAPID_EMAIL"),
        "environment_count": len(os.environ),
        "has_jwt_secret": bool(os.getenv("JWT_SECRET")),
        "environment_keys": [k for k in os.environ.keys() if not k.startswith('_')]
    }

# ✅ Debug endpoint to check database schema
@router.get("/webpush/debug-schema")
async def debug_webpush_schema(user=Depends(get_current_user)):
    """Debug endpoint to check webpush_subscriptions table schema"""
    conn = get_connection()
    cursor = conn.cursor()
    
    try:
        # Show table structure
        cursor.execute("DESCRIBE webpush_subscriptions")
        columns = cursor.fetchall()
        
        return {
            "table": "webpush_subscriptions",
            "columns": [{"field": col[0], "type": col[1], "null": col[2], "key": col[3]} for col in columns]
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Schema check failed: {str(e)}")
    finally:
        cursor.close()
        conn.close()

# ✅ NEW: Test notifications for threads and gear
@router.post("/webpush/test-branch-notification")
async def test_branch_notification(
    branch_id: int,
    message: str,
    user=Depends(get_current_user)
):
    """Test sending push notifications to all users in a branch"""
    if user.get("role") not in ["coach", "head_coach"]:
        raise HTTPException(status_code=403, detail="Only coaches can send test notifications")
    
    try:
        from app.services.notification_service import NotificationService
        result = await NotificationService.send_custom_notification(
            branch_id=branch_id,
            message=f"🧪 Test from {user['name']}: {message}",
            sender_id=user["id"]
        )
        
        return {
            "message": "Test notification sent",
            "sent": result["sent"],
            "failed": result["failed"]
        }
        
    except Exception as e:
        print(f"❌ Test notification error: {e}")
        raise HTTPException(status_code=500, detail=f"Test failed: {str(e)}")