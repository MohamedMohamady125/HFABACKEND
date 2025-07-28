# app/database.py - FIXED VERSION WITH CONNECTION POOLING
import mysql.connector
from mysql.connector import pooling
from contextlib import contextmanager
from app.config import settings
import logging
import time

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Connection pool configuration
DB_CONFIG = {
    'host': settings.DB_HOST,
    'user': settings.DB_USER,
    'password': settings.DB_PASSWORD,
    'database': settings.DB_NAME,
    'port': settings.DB_PORT,
    'pool_name': 'main_pool',
    'pool_size': 20,  # Increased for better performance
    'pool_reset_session': True,
    'autocommit': False,  # Changed to False for better transaction control
    'charset': 'utf8mb4',
    'use_unicode': True,
    'connect_timeout': 15,
    'sql_mode': 'STRICT_TRANS_TABLES'
}

# Create the connection pool
try:
    connection_pool = pooling.MySQLConnectionPool(**DB_CONFIG)
    logger.info("✅ Database connection pool created successfully")
except Exception as e:
    logger.error(f"❌ Failed to create connection pool: {e}")
    connection_pool = None

# LEGACY FUNCTION - Gradually replace all usages
def get_connection():
    """
    Legacy function - keeping for backward compatibility
    Gradually replace with get_db_cursor() context manager
    """
    start_time = time.time()
    try:
        if connection_pool:
            conn = connection_pool.get_connection()
        else:
            # Fallback to direct connection
            conn = mysql.connector.connect(
                host=settings.DB_HOST,
                user=settings.DB_USER,
                password=settings.DB_PASSWORD,
                database=settings.DB_NAME,
                port=settings.DB_PORT
            )
        
        connect_time = time.time() - start_time
        if connect_time > 0.1:  # Log slow connections
            logger.warning(f"⚠️ Slow connection: {connect_time:.3f}s")
        
        return conn
    except Exception as e:
        logger.error(f"❌ Connection failed: {e}")
        raise

@contextmanager
def get_db_connection():
    """
    Context manager for database connections with automatic cleanup
    USE THIS INSTEAD OF get_connection()!
    """
    connection = None
    try:
        if connection_pool:
            connection = connection_pool.get_connection()
        else:
            connection = mysql.connector.connect(**{k: v for k, v in DB_CONFIG.items() 
                                                  if k not in ['pool_name', 'pool_size', 'pool_reset_session']})
        yield connection
    except Exception as e:
        if connection:
            connection.rollback()
        logger.error(f"Database error: {e}")
        raise
    finally:
        if connection:
            connection.close()

@contextmanager
def get_db_cursor(dictionary=True):
    """
    Context manager for database cursor with automatic cleanup
    """
    with get_db_connection() as connection:
        cursor = connection.cursor(dictionary=dictionary)
        try:
            yield cursor, connection
        finally:
            cursor.close()

# Health check function
def check_database_health():
    """Check if database connection pool is healthy"""
    try:
        with get_db_cursor() as (cursor, connection):
            cursor.execute("SELECT 1")
            result = cursor.fetchone()
            return {"status": "healthy", "pool_size": connection_pool.pool_size if connection_pool else 0}
    except Exception as e:
        return {"status": "unhealthy", "error": str(e)}