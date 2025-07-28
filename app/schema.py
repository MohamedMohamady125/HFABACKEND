#!/usr/bin/env python3
"""
Database Schema Extractor
Extracts complete database schema and saves it to a file
"""

import mysql.connector
import json
from datetime import datetime

# Database Configuration (from your config)
DB_CONFIG = {
    'host': 'crossover.proxy.rlwy.net',
    'user': 'root',
    'password': 'omqxUvCPxFkGeCYjMYzfylckhYzcFwWV',
    'database': 'railway',
    'port': 42459
}

def get_database_connection():
    """Create database connection"""
    try:
        connection = mysql.connector.connect(**DB_CONFIG)
        return connection
    except Exception as e:
        print(f"❌ Error connecting to database: {e}")
        return None

def get_all_tables(cursor):
    """Get all table names"""
    cursor.execute("SHOW TABLES")
    tables = [table[0] for table in cursor.fetchall()]
    return tables

def get_table_structure(cursor, table_name):
    """Get detailed table structure"""
    cursor.execute(f"DESCRIBE {table_name}")
    columns = cursor.fetchall()
    
    # Convert to list of dictionaries for better readability
    table_structure = []
    for col in columns:
        table_structure.append({
            'Field': col[0],
            'Type': col[1],
            'Null': col[2],
            'Key': col[3],
            'Default': col[4],
            'Extra': col[5]
        })
    
    return table_structure

def get_foreign_keys(cursor):
    """Get all foreign key relationships"""
    query = """
    SELECT 
        TABLE_NAME,
        COLUMN_NAME,
        CONSTRAINT_NAME,
        REFERENCED_TABLE_NAME,
        REFERENCED_COLUMN_NAME
    FROM INFORMATION_SCHEMA.KEY_COLUMN_USAGE
    WHERE TABLE_SCHEMA = DATABASE()
    AND REFERENCED_TABLE_NAME IS NOT NULL
    ORDER BY TABLE_NAME, COLUMN_NAME
    """
    
    cursor.execute(query)
    foreign_keys = []
    for row in cursor.fetchall():
        foreign_keys.append({
            'table': row[0],
            'column': row[1],
            'constraint_name': row[2],
            'referenced_table': row[3],
            'referenced_column': row[4]
        })
    
    return foreign_keys

def get_existing_indexes(cursor):
    """Get all existing indexes"""
    query = """
    SELECT 
        TABLE_NAME,
        INDEX_NAME,
        COLUMN_NAME,
        SEQ_IN_INDEX,
        NON_UNIQUE
    FROM INFORMATION_SCHEMA.STATISTICS
    WHERE TABLE_SCHEMA = DATABASE()
    ORDER BY TABLE_NAME, INDEX_NAME, SEQ_IN_INDEX
    """
    
    cursor.execute(query)
    indexes = []
    for row in cursor.fetchall():
        indexes.append({
            'table': row[0],
            'index_name': row[1],
            'column': row[2],
            'sequence': row[3],
            'non_unique': bool(row[4])
        })
    
    return indexes

def get_table_create_statement(cursor, table_name):
    """Get CREATE TABLE statement"""
    cursor.execute(f"SHOW CREATE TABLE {table_name}")
    result = cursor.fetchone()
    return result[1] if result else None

def extract_complete_schema():
    """Extract complete database schema"""
    connection = get_database_connection()
    if not connection:
        return None
    
    try:
        cursor = connection.cursor()
        
        print("🔍 Extracting database schema...")
        
        # Get all tables
        tables = get_all_tables(cursor)
        print(f"📊 Found {len(tables)} tables")
        
        # Build complete schema
        schema = {
            'extraction_date': datetime.now().isoformat(),
            'database_name': DB_CONFIG['database'],
            'total_tables': len(tables),
            'tables': {},
            'foreign_keys': get_foreign_keys(cursor),
            'existing_indexes': get_existing_indexes(cursor)
        }
        
        # Get structure for each table
        for table in tables:
            print(f"  📋 Processing table: {table}")
            schema['tables'][table] = {
                'structure': get_table_structure(cursor, table),
                'create_statement': get_table_create_statement(cursor, table)
            }
        
        cursor.close()
        connection.close()
        
        return schema
        
    except Exception as e:
        print(f"❌ Error extracting schema: {e}")
        if connection:
            connection.close()
        return None

def save_schema_to_file(schema, filename='database_schema.json'):
    """Save schema to JSON file"""
    try:
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(schema, f, indent=2, default=str)
        print(f"✅ Schema saved to {filename}")
        return True
    except Exception as e:
        print(f"❌ Error saving schema: {e}")
        return False

def print_schema_summary(schema):
    """Print a summary of the schema"""
    print("\n" + "="*60)
    print("📊 DATABASE SCHEMA SUMMARY")
    print("="*60)
    print(f"Database: {schema['database_name']}")
    print(f"Total Tables: {schema['total_tables']}")
    print(f"Total Foreign Keys: {len(schema['foreign_keys'])}")
    print(f"Total Indexes: {len(schema['existing_indexes'])}")
    
    print("\n📋 TABLES:")
    for table_name, table_info in schema['tables'].items():
        column_count = len(table_info['structure'])
        print(f"  • {table_name} ({column_count} columns)")
    
    print("\n🔗 FOREIGN KEY RELATIONSHIPS:")
    for fk in schema['foreign_keys']:
        print(f"  • {fk['table']}.{fk['column']} → {fk['referenced_table']}.{fk['referenced_column']}")
    
    print("\n📊 EXISTING INDEXES:")
    current_table = None
    for idx in schema['existing_indexes']:
        if idx['table'] != current_table:
            current_table = idx['table']
            print(f"  📋 {current_table}:")
        index_type = "UNIQUE" if not idx['non_unique'] else "INDEX"
        print(f"    • {idx['index_name']} ({index_type}) on {idx['column']}")

def main():
    """Main function"""
    print("🚀 Starting database schema extraction...")
    
    # Extract schema
    schema = extract_complete_schema()
    if not schema:
        print("❌ Failed to extract schema")
        return
    
    # Save to file
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"database_schema_{timestamp}.json"
    
    if save_schema_to_file(schema, filename):
        print_schema_summary(schema)
        print(f"\n✅ Complete schema extracted and saved to: {filename}")
        print("\n📝 You can now share this file to get optimized indexes!")
    else:
        print("❌ Failed to save schema file")

if __name__ == "__main__":
    main()