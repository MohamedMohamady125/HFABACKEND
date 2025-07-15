import mysql.connector
import os

# --- Configuration ---
DB_CONFIG = {
    'host': 'localhost',
    'port': 3306,
    'user': 'root',
    'password': 'MmmM12345!',
    'database': 'hfa' # You can comment this out to get all databases
}

OUTPUT_FILE = 'database_schema.sql'
# -------------------

def get_mysql_schema(config, output_file):
    """
    Connects to a MySQL database and extracts the schema (DDL for tables)
    for the specified database or all databases if 'database' is not in config.
    Writes the schema to the given output file.
    """
    try:
        conn = mysql.connector.connect(**config)
        cursor = conn.cursor()

        schema_content = []

        if 'database' in config and config['database']:
            databases_to_process = [config['database']]
        else:
            # Get all user databases (excluding system databases)
            cursor.execute("SHOW DATABASES;")
            all_databases = [db[0] for db in cursor if db[0] not in ('information_schema', 'mysql', 'performance_schema', 'sys')]
            databases_to_process = all_databases

        for db_name in databases_to_process:
            print(f"Extracting schema for database: {db_name}")
            schema_content.append(f"-- Schema for database: {db_name}\n")
            cursor.execute(f"USE {db_name};")

            # Get table DDL
            cursor.execute("SHOW TABLES;")
            tables = [table[0] for table in cursor]

            if not tables:
                schema_content.append(f"-- No tables found in database: {db_name}\n\n")
                continue

            for table_name in tables:
                cursor.execute(f"SHOW CREATE TABLE `{table_name}`;")
                create_table_statement = cursor.fetchone()[1]
                schema_content.append(f"{create_table_statement};\n\n")

        with open(output_file, 'w', encoding='utf-8') as f:
            f.writelines(schema_content)

        print(f"Successfully extracted schema to '{output_file}'")

    except mysql.connector.Error as err:
        print(f"Error: {err}")
    finally:
        if 'conn' in locals() and conn.is_connected():
            cursor.close()
            conn.close()
            print("Database connection closed.")

if __name__ == "__main__":
    # Ensure the output directory exists if specified
    output_dir = os.path.dirname(OUTPUT_FILE)
    if output_dir and not os.path.exists(output_dir):
        os.makedirs(output_dir)

    get_mysql_schema(DB_CONFIG, OUTPUT_FILE)