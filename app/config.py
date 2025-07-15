import os
from dotenv import load_dotenv

load_dotenv()

class Settings:
    def __init__(self):
        # Use Railway's built-in MySQL variables directly
        self.DB_HOST = os.environ.get("MYSQLHOST", "mysql.railway.internal")
        self.DB_USER = os.environ.get("MYSQLUSER", "root")
        self.DB_PASSWORD = os.environ.get("MYSQL_ROOT_PASSWORD", "")
        self.DB_NAME = os.environ.get("MYSQL_DATABASE", "railway")
        self.JWT_SECRET = os.environ.get("JWT_SECRET")
        self.JWT_ALGORITHM = os.environ.get("JWT_ALGORITHM")
        self.SENDGRID_API_KEY = os.environ.get("SENDGRID_API_KEY")
        self.FROM_EMAIL = os.environ.get("FROM_EMAIL")
        
        # Debug output
        print(f"🔍 Using MYSQLHOST: {self.DB_HOST}")
        print(f"🔍 Using MYSQLUSER: {self.DB_USER}")
        print(f"🔍 Using MYSQL_DATABASE: {self.DB_NAME}")

settings = Settings()