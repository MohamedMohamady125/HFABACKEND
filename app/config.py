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
        self.JWT_SECRET = os.environ.get("JWT_SECRET")
        self.JWT_ALGORITHM = os.environ.get("JWT_ALGORITHM")
        self.SENDGRID_API_KEY = os.environ.get("SENDGRID_API_KEY")
        self.FROM_EMAIL = os.environ.get("FROM_EMAIL")
        
        print(f"🔍 DB_HOST: {self.DB_HOST}")
        print(f"🔍 DB_PORT: {self.DB_PORT}")

settings = Settings()