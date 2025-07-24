# app/config.py - FIXED VERSION
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

class Settings:
    def __init__(self):
        # Database Configuration
        self.DB_HOST = "crossover.proxy.rlwy.net"
        self.DB_USER = "root"
        self.DB_PASSWORD = "omqxUvCPxFkGeCYjMYzfylckhYzcFwWV"
        self.DB_NAME = "railway"
        self.DB_PORT = 42459
        
        # JWT Configuration - FIXED
        self.JWT_SECRET = os.getenv("JWT_SECRET", "my-local-super-secret-key-123")
        self.JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
        
        # Email Configuration
        self.SENDGRID_API_KEY = os.getenv("SENDGRID_API_KEY")
        self.FROM_EMAIL = os.getenv("FROM_EMAIL")
        
        # Debug output
        print("=" * 50)
        print("🔧 FASTAPI CONFIGURATION")
        print("=" * 50)
        print(f"🔍 DB_HOST: {self.DB_HOST}")
        print(f"🔍 DB_PORT: {self.DB_PORT}")
        print(f"🔍 JWT_SECRET: {self.JWT_SECRET}")
        print(f"🔍 JWT_ALGORITHM: {self.JWT_ALGORITHM}")
        print(f"🔍 JWT_SECRET length: {len(self.JWT_SECRET)}")
        print("=" * 50)

# Create global settings instance
settings = Settings()