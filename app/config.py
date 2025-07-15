import os
from dotenv import load_dotenv

load_dotenv()

class Settings:
    def __init__(self):
        # Use public MySQL connection temporarily
        self.DB_HOST = "crossover.proxy.rlwy.net"
        self.DB_USER = "root"
        self.DB_PASSWORD = "omqxUvCPxFkGeCYjMYzfylckhYzcFwWV"
        self.DB_NAME = "railway"
        self.DB_PORT = 42459
        
        # JWT Configuration with fallbacks and debug
        self.JWT_SECRET = os.environ.get("JWT_SECRET", "hfa-super-secret-jwt-key-2025-production-railway")
        self.JWT_ALGORITHM = os.environ.get("JWT_ALGORITHM", "HS256")
        
        self.SENDGRID_API_KEY = os.environ.get("SENDGRID_API_KEY")
        self.FROM_EMAIL = os.environ.get("FROM_EMAIL")
        
        # Debug output
        print(f"🔍 DB_HOST: {self.DB_HOST}")
        print(f"🔍 DB_PORT: {self.DB_PORT}")
        print(f"🔍 JWT_SECRET loaded: {'Yes' if self.JWT_SECRET else 'NO'}")
        print(f"🔍 JWT_ALGORITHM: {self.JWT_ALGORITHM}")
        print(f"🔍 JWT_SECRET length: {len(self.JWT_SECRET) if self.JWT_SECRET else 0}")

settings = Settings()