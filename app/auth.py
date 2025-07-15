# app/auth.py - FIXED VERSION WITH PROPER IMPORTS

from typing import Optional
import re
import random
import string
from datetime import datetime, timedelta

from fastapi import APIRouter, HTTPException, status, Depends
from pydantic import BaseModel, EmailStr, Field, validator
from app.database import get_connection
from app.schemas import UserCreate, UserLogin
from jose import jwt
from app.config import settings
from passlib.hash import bcrypt
from app.deps import get_current_user

# ✅ FIXED: Import the correct email function
from app.utils.email import send_reset_code_email

router = APIRouter()

# =================== HELPER FUNCTIONS ===================

def generate_reset_code(length=6):
    """Generate a numeric reset code of given length (default 6)."""
    return ''.join([str(random.randint(0, 9)) for _ in range(length)])

# =================== PYDANTIC MODELS ===================

class ForgotPasswordRequest(BaseModel):
    email: EmailStr

class VerifyResetCodeRequest(BaseModel):
    email: EmailStr
    code: str = Field(..., min_length=4, max_length=8, description="The reset code sent to email")

class ResetPasswordRequest(BaseModel):
    email: EmailStr
    code: str = Field(..., min_length=4, max_length=8, description="The reset code sent to email")
    new_password: str = Field(..., min_length=8, max_length=128)
    confirm_password: str = Field(..., min_length=8, max_length=128)

    @validator('confirm_password')
    def passwords_match(cls, v, values):
        if 'new_password' in values and v != values['new_password']:
            raise ValueError('Passwords do not match')
        return v

class AthleteRegistration(BaseModel):
    name: str = Field(..., min_length=2, max_length=50, description="Full name")
    email: EmailStr = Field(..., description="Email address")
    phone: str = Field(..., description="Egyptian phone number")
    password: str = Field(..., min_length=8, max_length=128, description="Password")
    branch_id: int = Field(..., description="Branch ID")
    branch_name: Optional[str] = Field(None, description="Branch name (optional, for compatibility)")

    @validator('name')
    def validate_name(cls, v):
        if not v or not v.strip():
            raise ValueError('Name is required')
        
        name = v.strip()
        
        # Check length
        if len(name) < 2:
            raise ValueError('Name must be at least 2 characters')
        if len(name) > 50:
            raise ValueError('Name must be less than 50 characters')
        
        # Only allow letters, spaces, hyphens, dots, and Arabic characters
        if not re.match(r'^[a-zA-Z\u0600-\u06FF\s\-\.]+$', name):
            raise ValueError('Name can only contain letters, spaces, hyphens, and dots')
        
        return name

    @validator('email')
    def validate_email_format(cls, v):
        if not v or not v.strip():
            raise ValueError('Email is required')
        
        email = v.strip().lower()
        return email

    @validator('phone')
    def validate_egyptian_phone(cls, v):
        if not v or not v.strip():
            raise ValueError('Phone number is required')
        
        # Remove all non-digits
        digits_only = re.sub(r'[^\d]', '', str(v))
        
        # Egyptian phone number validation
        if len(digits_only) < 10 or len(digits_only) > 11:
            raise ValueError('Egyptian phone number must be 10-11 digits')
        
        # Must start with 0
        if not digits_only.startswith('0'):
            raise ValueError('Egyptian phone number must start with 0')
        
        # Mobile numbers validation (01x)
        if digits_only.startswith('01'):
            if len(digits_only) != 11:
                raise ValueError('Mobile number must be 11 digits (01xxxxxxxxx)')
            # Valid mobile prefixes in Egypt: 010, 011, 012, 015
            valid_mobile_prefixes = ['010', '011', '012', '015']
            prefix = digits_only[:3]
            if prefix not in valid_mobile_prefixes:
                raise ValueError('Invalid mobile prefix. Use 010, 011, 012, or 015')
        # Landline validation (0xx)
        elif digits_only.startswith('0') and not digits_only.startswith('01'):
            if len(digits_only) < 10 or len(digits_only) > 11:
                raise ValueError('Landline number must be 10-11 digits')
        else:
            raise ValueError('Invalid Egyptian phone number format')
        
        return digits_only

    @validator('password')
    def validate_password_strength(cls, v):
        if not v:
            raise ValueError('Password is required')
        
        if len(v) < 8:
            raise ValueError('Password must be at least 8 characters')
        if len(v) > 128:
            raise ValueError('Password must be less than 128 characters')
        
        # Check for at least one uppercase letter
        if not re.search(r'[A-Z]', v):
            raise ValueError('Password must contain at least one uppercase letter')
        
        # Check for at least one lowercase letter
        if not re.search(r'[a-z]', v):
            raise ValueError('Password must contain at least one lowercase letter')
        
        # Check for at least one digit
        if not re.search(r'[0-9]', v):
            raise ValueError('Password must contain at least one number')
        
        return v

    class Config:
        validate_assignment = True

class ChangePasswordRequest(BaseModel):
    current_password: str = Field(..., min_length=1, description="Current password")
    new_password: str = Field(..., min_length=6, description="New password (minimum 6 characters)")
    confirm_password: str = Field(..., min_length=6, description="Confirm new password")

# =================== REGISTRATION ENDPOINT ===================

@router.post("/register")
def register_athlete(user: AthleteRegistration):
    """Enhanced athlete registration with comprehensive validation"""
    conn = get_connection()
    cursor = conn.cursor(dictionary=True, buffered=True)

    try:
        print(f"🔄 Processing registration for: {user.email}")
        
        # 1. Check if email already exists in users table
        cursor.execute("SELECT id, email FROM users WHERE email = %s", (user.email,))
        existing_user = cursor.fetchone()
        if existing_user:
            print(f"❌ Email already exists in users: {user.email}")
            raise HTTPException(
                status_code=400, 
                detail="Email address is already registered"
            )
        
        # 2. Check if email already exists in registration_requests table
        cursor.execute("SELECT id, email FROM registration_requests WHERE email = %s", (user.email,))
        existing_request = cursor.fetchone()
        if existing_request:
            print(f"❌ Email already has pending request: {user.email}")
            raise HTTPException(
                status_code=400, 
                detail="Email already has a pending registration request"
            )
        
        # 3. Check if phone number already exists in users table
        cursor.execute("SELECT id, phone FROM users WHERE phone = %s", (user.phone,))
        existing_phone_user = cursor.fetchone()
        if existing_phone_user:
            print(f"❌ Phone already exists in users: {user.phone}")
            raise HTTPException(
                status_code=400, 
                detail="Phone number is already registered"
            )
        
        # 4. Check if phone number already exists in registration_requests table
        cursor.execute("SELECT id, phone FROM registration_requests WHERE phone = %s", (user.phone,))
        existing_phone_request = cursor.fetchone()
        if existing_phone_request:
            print(f"❌ Phone already has pending request: {user.phone}")
            raise HTTPException(
                status_code=400, 
                detail="Phone number already has a pending registration request"
            )
        
        # 5. Verify branch exists and get branch information
        cursor.execute("SELECT id, name FROM branches WHERE id = %s", (user.branch_id,))
        branch = cursor.fetchone()
        if not branch:
            print(f"❌ Branch not found: {user.branch_id}")
            raise HTTPException(
                status_code=400, 
                detail="Selected branch does not exist"
            )
        
        branch_name = branch["name"]
        print(f"✅ Valid branch selected: {branch_name} (ID: {user.branch_id})")
        
        # 6. Hash the password
        password_hash = bcrypt.hash(user.password)
        print(f"✅ Password hashed successfully")
        
        # 7. Insert registration request
        cursor.execute("""
            INSERT INTO registration_requests 
            (athlete_name, phone, email, password_hash, branch_name) 
            VALUES (%s, %s, %s, %s, %s)
        """, (
            user.name,
            user.phone,
            user.email,
            password_hash,
            branch_name
        ))
        
        request_id = cursor.lastrowid
        print(f"✅ Registration request created with ID: {request_id}")
        print(f"✅ Branch name saved: {branch_name}")
        
        # 8. Notify ONLY coaches in the selected branch
        cursor.execute("""
            SELECT id, name, email FROM users 
            WHERE role IN ('coach', 'head_coach') AND branch_id = %s
        """, (user.branch_id,))
        branch_coaches = cursor.fetchall()
        
        notification_message = f"New registration request from {user.name} for {branch_name} branch"
        
        # Insert notifications ONLY for coaches in the specific branch
        for coach in branch_coaches:
            cursor.execute("""
                INSERT INTO notifications (user_id, message, type) 
                VALUES (%s, %s, %s)
            """, (coach["id"], notification_message, "reg_request"))
        
        print(f"✅ Notified {len(branch_coaches)} coach(es) in {branch_name} branch ONLY about registration request from {user.name}")
        
        # 9. Commit transaction
        conn.commit()
        
        print(f"✅ Registration completed successfully for {user.email}")
        
        return {
            "success": True,
            "message": f"Registration request submitted successfully for {branch_name} branch. A coach will review and approve your request.",
            "data": {
                "request_id": request_id,
                "athlete_name": user.name,
                "email": user.email,
                "branch_name": branch_name,
                "status": "pending_approval"
            }
        }
        
    except HTTPException:
        conn.rollback()
        raise
    except Exception as e:
        conn.rollback()
        print(f"❌ Unexpected error during registration: {e}")
        import traceback
        print(f"❌ Full traceback: {traceback.format_exc()}")
        raise HTTPException(
            status_code=500, 
            detail="Registration failed due to server error. Please try again."
        )
    finally:
        cursor.close()
        conn.close()

# =================== LOGIN ENDPOINT ===================

@router.post("/login")
def login(user: UserLogin):
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    print("🧪 Attempting login for:", user.email)

    try:
        cursor.execute("SELECT * FROM users WHERE email = %s", (user.email,))
        db_user = cursor.fetchone()

        if not db_user or not bcrypt.verify(user.password, db_user["password_hash"]):
            raise HTTPException(status_code=401, detail="Invalid email or password")

        # Auto-insert into athletes table if role is athlete and approved
        if db_user["role"] == "athlete" and db_user.get("approved", False):
            cursor.execute("SELECT 1 FROM athletes WHERE user_id = %s", (db_user["id"],))
            if not cursor.fetchone():
                cursor.execute("INSERT INTO athletes (id, user_id) VALUES (%s, %s)", (db_user["id"], db_user["id"]))
                conn.commit()

        token = jwt.encode(
            {"sub": str(db_user["id"])},
            settings.JWT_SECRET,
            algorithm=settings.JWT_ALGORITHM,
        )

        return {
            "token": token,
            "user": {
                "id": db_user["id"],
                "name": db_user["name"],
                "email": db_user["email"],
                "phone": db_user["phone"],
                "role": db_user["role"],
                "approved": db_user.get("approved", False),
            },
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Login failed: {e}")
    finally:
        cursor.close()
        conn.close()

# =================== FORGOT PASSWORD ENDPOINTS ===================

@router.post("/forgot-password", status_code=status.HTTP_200_OK)
def forgot_password(data: ForgotPasswordRequest):
    """Send a 6-digit verification code to user's email for password reset"""
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        print(f"🔄 Step 1: Processing forgot password request for: {data.email}")

        # Check if user exists
        cursor.execute("SELECT id, name, email FROM users WHERE email = %s", (data.email,))
        user = cursor.fetchone()
        print(f"🔄 Step 2: User query result: {user}")

        if not user:
            print(f"❌ Step 2: Email not found: {data.email}")
            return {"success": True, "detail": "If the account exists, a reset code will be sent."}

        user_name = user["name"]
        print(f"🔄 Step 3: User found: {user_name}")

        # Generate 6-digit code
        reset_code = generate_reset_code()
        print(f"🔑 Step 4: Generated reset code: {reset_code} for {data.email}")
        
        # Set expiration time (15 minutes from now)
        expires_at = datetime.now() + timedelta(minutes=15)
        print(f"🔄 Step 5: Code expires at: {expires_at}")

        # Delete any existing codes for this email
        cursor.execute("DELETE FROM password_reset_otps WHERE email = %s", (data.email,))
        print(f"🔄 Step 6: Deleted existing codes for {data.email}")

        # Insert new reset code using your table structure
        cursor.execute("""
            INSERT INTO password_reset_otps (email, otp_code, expires_at)
            VALUES (%s, %s, %s)
        """, (data.email, reset_code, expires_at))
        print(f"🔄 Step 7: Inserted new code into database")

        conn.commit()
        print(f"✅ Step 8: Database committed successfully")

        # ✅ FIXED: Send email with proper error handling
        try:
            print(f"🔄 Step 9: Attempting to send email...")
            send_reset_code_email(data.email, user_name, reset_code)
            print(f"✅ Step 10: Email sent successfully to {data.email}")
        except Exception as email_error:
            print(f"❌ Email sending error: {email_error}")
            # Delete the code if email failed
            cursor.execute("DELETE FROM password_reset_otps WHERE email = %s AND otp_code = %s", (data.email, reset_code))
            conn.commit()
            raise HTTPException(status_code=500, detail=f"Failed to send email: {email_error}")

        return {
            "success": True,
            "detail": "Reset code sent to your email. Code expires in 15 minutes.",
            "debug_info": {
                "email": data.email,
                "code": reset_code,  # ✅ For testing - remove in production
                "expires_at": expires_at.isoformat()
            }
        }

    except HTTPException:
        conn.rollback()
        raise
    except Exception as e:
        conn.rollback()
        print(f"❌ ERROR in forgot_password: {e}")
        print(f"❌ ERROR type: {type(e)}")
        import traceback
        print(f"❌ Full traceback: {traceback.format_exc()}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to process reset request: {str(e)}"
        )
    finally:
        cursor.close()
        conn.close()

@router.post("/verify-reset-code", status_code=status.HTTP_200_OK)
def verify_reset_code(data: VerifyResetCodeRequest):
    """Verify the 6-digit reset code before allowing password reset"""
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        print(f"🔄 Verifying reset code for: {data.email}")
        print(f"🔑 Code provided: {data.code}")

        # Clean up expired codes first
        cursor.execute("DELETE FROM password_reset_otps WHERE expires_at < NOW()")

        # Find valid reset code using your table structure
        cursor.execute("""
            SELECT prt.*, u.name 
            FROM password_reset_otps prt
            JOIN users u ON prt.email = u.email
            WHERE prt.email = %s AND prt.otp_code = %s 
            AND prt.expires_at > NOW()
        """, (data.email, data.code))

        code_record = cursor.fetchone()

        if not code_record:
            print(f"❌ Invalid or expired code for {data.email}")
            raise HTTPException(
                status_code=400,
                detail="Invalid or expired reset code"
            )

        print(f"✅ Valid reset code verified for {data.email}")

        return {
            "success": True,
            "detail": "Reset code verified successfully. You can now reset your password.",
            "user_name": code_record["name"]
        }

    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error verifying reset code: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to verify reset code"
        )
    finally:
        cursor.close()
        conn.close()

@router.post("/reset-password", status_code=status.HTTP_200_OK)
def reset_password(data: ResetPasswordRequest):
    """Reset password using verified code and new password"""
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        print(f"🔄 Resetting password for: {data.email}")

        # Clean up expired codes first
        cursor.execute("DELETE FROM password_reset_otps WHERE expires_at < NOW()")

        # Find valid reset code using your table structure
        cursor.execute("""
            SELECT prt.*, u.id as user_id, u.name 
            FROM password_reset_otps prt
            JOIN users u ON prt.email = u.email
            WHERE prt.email = %s AND prt.otp_code = %s 
            AND prt.expires_at > NOW()
        """, (data.email, data.code))

        code_record = cursor.fetchone()

        if not code_record:
            print(f"❌ Invalid or expired code for {data.email}")
            raise HTTPException(
                status_code=400,
                detail="Invalid or expired reset code"
            )

        user_id = code_record["user_id"]
        user_name = code_record["name"]

        # Hash the new password
        new_password_hash = bcrypt.hash(data.new_password)

        # Update user's password
        cursor.execute("""
            UPDATE users 
            SET password_hash = %s 
            WHERE id = %s
        """, (new_password_hash, user_id))

        # Delete the used reset code
        cursor.execute("""
            DELETE FROM password_reset_otps
            WHERE email = %s AND otp_code = %s
        """, (data.email, data.code))

        conn.commit()

        print(f"✅ Password reset successfully for {data.email} (User: {user_name})")

        return {
            "success": True,
            "detail": "Password reset successfully. You can now login with your new password.",
            "user_name": user_name
        }

    except HTTPException:
        conn.rollback()
        raise
    except Exception as e:
        conn.rollback()
        print(f"❌ Error resetting password: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to reset password"
        )
    finally:
        cursor.close()
        conn.close()

# =================== CHANGE PASSWORD ENDPOINT ===================

@router.post("/change-password")
def change_password(data: ChangePasswordRequest, user=Depends(get_current_user)):
    """Change user password after validating current password"""
    # Validate that new passwords match
    if data.new_password != data.confirm_password:
        raise HTTPException(
            status_code=400,
            detail="New password and confirmation do not match"
        )

    # Validate new password is different from current
    if data.current_password == data.new_password:
        raise HTTPException(
            status_code=400,
            detail="New password must be different from current password"
        )

    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        # Get current user's password hash
        cursor.execute(
            "SELECT password_hash FROM users WHERE id = %s",
            (user["id"],)
        )
        user_data = cursor.fetchone()

        if not user_data:
            raise HTTPException(status_code=404, detail="User not found")

        # Verify current password
        if not bcrypt.verify(data.current_password, user_data["password_hash"]):
            raise HTTPException(
                status_code=400,
                detail="Current password is incorrect"
            )

        # Hash new password
        new_password_hash = bcrypt.hash(data.new_password)

        # Update password in database
        cursor.execute(
            "UPDATE users SET password_hash = %s WHERE id = %s",
            (new_password_hash, user["id"])
        )

        conn.commit()

        print(f"✅ Password changed successfully for user {user['id']}")

        return {
            "success": True,
            "message": "Password changed successfully"
        }

    except HTTPException:
        raise
    except Exception as e:
        conn.rollback()
        print(f"❌ Error changing password: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to change password"
        )
    finally:
        cursor.close()
        conn.close()