# app/deps.py - FIXED VERSION
from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt, JWTError
from app.config import settings
from app.database import get_connection

# Create HTTPBearer security scheme
security = HTTPBearer()

def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Extract and validate JWT token, return user info"""
    
    token = credentials.credentials
    
    # ✅ FIXED: Clean up token - remove extra quotes and whitespace
    if token:
        token = token.strip()
        if token.startswith('"') and token.endswith('"'):
            token = token[1:-1]  # Remove surrounding quotes
            print(f"🔧 Removed extra quotes from token")
    
    print(f"🔍 Token received: {repr(token[:20])}..." if token else "❌ No token")
    print(f"🔍 JWT_SECRET being used: {settings.JWT_SECRET[:10]}..." if settings.JWT_SECRET else "❌ No JWT_SECRET")
    print(f"🔍 JWT_ALGORITHM: {settings.JWT_ALGORITHM}")
    
    try:
        # Decode JWT token
        payload = jwt.decode(
            token, 
            settings.JWT_SECRET, 
            algorithms=[settings.JWT_ALGORITHM]
        )
        
        user_id = payload.get("sub")
        print(f"✅ JWT decoded successfully, user_id: {user_id}")
        
        if user_id is None:
            print("❌ No 'sub' field in JWT payload")
            raise HTTPException(
                status_code=401, 
                detail="Invalid token: no user ID"
            )
        
    except JWTError as e:
        print(f"❌ JWT decode error: {e}")
        raise HTTPException(
            status_code=401, 
            detail="Could not validate token"
        )
    except Exception as e:
        print(f"❌ Unexpected error decoding JWT: {e}")
        raise HTTPException(
            status_code=401, 
            detail="Token validation failed"
        )
    
    # Get user from database
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    
    try:
        cursor.execute("SELECT * FROM users WHERE id = %s", (user_id,))
        user = cursor.fetchone()
        
        if not user:
            print(f"❌ User not found in database: {user_id}")
            raise HTTPException(
                status_code=404, 
                detail="User not found"
            )
        
        print(f"✅ User found: {user['name']} ({user['email']})")
        return user
        
    except Exception as e:
        print(f"❌ Database error: {e}")
        raise HTTPException(
            status_code=500, 
            detail="Database error"
        )
    finally:
        cursor.close()
        conn.close()