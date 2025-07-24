# app/services/notification_service.py
import os
from typing import Optional
from pywebpush import webpush, WebPushException
from app.database import get_connection
from dotenv import load_dotenv

load_dotenv()

# VAPID Configuration
VAPID_PRIVATE_KEY = os.getenv("VAPID_PRIVATE_KEY")
VAPID_PUBLIC_KEY = os.getenv("VAPID_PUBLIC_KEY")

class NotificationService:
    
    @staticmethod
    def _send_push_notification(endpoint: str, p256dh: str, auth: str, message: str) -> bool:
        """Send a single push notification"""
        try:
            subscription_info = {
                "endpoint": endpoint,
                "keys": {
                    "p256dh": p256dh,
                    "auth": auth
                }
            }
            
            # ✅ Extract origin from endpoint for correct aud claim
            from urllib.parse import urlparse
            parsed_endpoint = urlparse(endpoint)
            origin = f"{parsed_endpoint.scheme}://{parsed_endpoint.netloc}"
            
            # Use dynamic VAPID claims with correct audience
            dynamic_vapid_claims = {
                "sub": os.getenv("VAPID_EMAIL", "mailto:mohamadhany97@gmail.com"),
                "aud": origin
            }
            
            webpush(
                subscription_info=subscription_info,
                data=message,
                vapid_private_key=VAPID_PRIVATE_KEY,
                vapid_claims=dynamic_vapid_claims  # ← Use dynamic claims instead of static
            )
            return True
            
        except WebPushException as e:
            print(f"⚠️ Push notification failed: {e}")
            return False
        except Exception as e:
            print(f"❌ Unexpected push error: {e}")
            return False
    
    @staticmethod
    def _get_branch_users_with_subscriptions(branch_id: int, exclude_user_id: int):
        """Get all users in a branch with their push subscriptions, excluding the sender"""
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        
        try:
            cursor.execute("""
                SELECT DISTINCT 
                    u.id as user_id,
                    u.name,
                    u.role,
                    ws.endpoint,
                    ws.p256dh,
                    ws.auth
                FROM users u
                LEFT JOIN webpush_subscriptions ws ON u.id = ws.user_id
                WHERE u.branch_id = %s 
                AND u.id != %s
                AND u.approved = 1
                AND ws.endpoint IS NOT NULL
                ORDER BY u.name
            """, (branch_id, exclude_user_id))
            
            return cursor.fetchall()
            
        except Exception as e:
            print(f"❌ Error getting branch users: {e}")
            return []
        finally:
            cursor.close()
            conn.close()
    
    @staticmethod
    async def send_thread_notification(thread_id: int, sender_id: int, message_preview: str):
        """Send push notifications for new thread messages"""
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        
        try:
            # Get thread and branch info
            cursor.execute("""
                SELECT t.branch_id, t.title, b.name as branch_name, u.name as sender_name
                FROM threads t
                JOIN branches b ON t.branch_id = b.id
                JOIN users u ON u.id = %s
                WHERE t.id = %s
            """, (sender_id, thread_id))
            
            thread_info = cursor.fetchone()
            if not thread_info:
                print(f"❌ Thread {thread_id} not found")
                return
            
            branch_id = thread_info["branch_id"]
            branch_name = thread_info["branch_name"]
            sender_name = thread_info["sender_name"]
            thread_title = thread_info["title"]
            
            # Get all branch users with subscriptions (excluding sender)
            recipients = NotificationService._get_branch_users_with_subscriptions(branch_id, sender_id)
            
            if not recipients:
                print(f"ℹ️ No users with push subscriptions in branch {branch_name}")
                return
            
            # Create notification message
            preview = message_preview[:50] + "..." if len(message_preview) > 50 else message_preview
            notification_message = f"💬 {sender_name} in {thread_title}: {preview}"
            
            # Send push notifications
            sent_count = 0
            failed_count = 0
            
            for recipient in recipients:
                success = NotificationService._send_push_notification(
                    endpoint=recipient["endpoint"],
                    p256dh=recipient["p256dh"],
                    auth=recipient["auth"],
                    message=notification_message
                )
                
                if success:
                    sent_count += 1
                    print(f"✅ Push sent to {recipient['name']} ({recipient['role']})")
                else:
                    failed_count += 1
                    print(f"❌ Push failed for {recipient['name']}")
            
            print(f"📊 Thread notification summary: {sent_count} sent, {failed_count} failed")
            
        except Exception as e:
            print(f"❌ Error sending thread notifications: {e}")
        finally:
            cursor.close()
            conn.close()
    
    @staticmethod
    async def send_gear_notification(branch_id: int, sender_id: int):
        """Send push notifications for gear updates"""
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        
        try:
            # Get branch and sender info
            cursor.execute("""
                SELECT b.name as branch_name, u.name as sender_name, u.role as sender_role
                FROM branches b
                JOIN users u ON u.id = %s
                WHERE b.id = %s
            """, (sender_id, branch_id))
            
            info = cursor.fetchone()
            if not info:
                print(f"❌ Branch {branch_id} or sender {sender_id} not found")
                return
            
            branch_name = info["branch_name"]
            sender_name = info["sender_name"]
            sender_role = info["sender_role"]
            
            # Get all branch users with subscriptions (excluding sender)
            recipients = NotificationService._get_branch_users_with_subscriptions(branch_id, sender_id)
            
            if not recipients:
                print(f"ℹ️ No users with push subscriptions in branch {branch_name}")
                return
            
            # Create notification message
            role_display = "Head Coach" if sender_role == "head_coach" else "Coach"
            notification_message = f"🎽 {role_display} {sender_name} updated gear for {branch_name}"
            
            # Send push notifications
            sent_count = 0
            failed_count = 0
            
            for recipient in recipients:
                success = NotificationService._send_push_notification(
                    endpoint=recipient["endpoint"],
                    p256dh=recipient["p256dh"],
                    auth=recipient["auth"],
                    message=notification_message
                )
                
                if success:
                    sent_count += 1
                    print(f"✅ Gear push sent to {recipient['name']} ({recipient['role']})")
                else:
                    failed_count += 1
                    print(f"❌ Gear push failed for {recipient['name']}")
            
            print(f"📊 Gear notification summary: {sent_count} sent, {failed_count} failed")
            
        except Exception as e:
            print(f"❌ Error sending gear notifications: {e}")
        finally:
            cursor.close()
            conn.close()
    
    @staticmethod
    async def send_custom_notification(branch_id: int, message: str, sender_id: Optional[int] = None):
        """Send custom push notifications to all branch users"""
        try:
            # Get all branch users with subscriptions (excluding sender if provided)
            exclude_id = sender_id if sender_id else -1
            recipients = NotificationService._get_branch_users_with_subscriptions(branch_id, exclude_id)
            
            if not recipients:
                print(f"ℹ️ No users with push subscriptions in branch {branch_id}")
                return {"sent": 0, "failed": 0}
            
            # Send push notifications
            sent_count = 0
            failed_count = 0
            
            for recipient in recipients:
                success = NotificationService._send_push_notification(
                    endpoint=recipient["endpoint"],
                    p256dh=recipient["p256dh"],
                    auth=recipient["auth"],
                    message=message
                )
                
                if success:
                    sent_count += 1
                else:
                    failed_count += 1
            
            print(f"📊 Custom notification summary: {sent_count} sent, {failed_count} failed")
            return {"sent": sent_count, "failed": failed_count}
            
        except Exception as e:
            print(f"❌ Error sending custom notifications: {e}")
            return {"sent": 0, "failed": 0, "error": str(e)}