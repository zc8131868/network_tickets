#!/usr/bin/env python3
"""
Script to create MySQL user chris123 with permissions to edit auto_tickets_itsr_network table
Usage: python create_chris123_user.py
"""

import pymysql
import sys

# Database connection parameters
DB_HOST = '172.19.11.14'
DB_USER = 'root'
DB_PASSWORD = 'zc8131868'
DB_NAME = 'auto_tickets'
TABLE_NAME = 'auto_tickets_itsr_network'

NEW_USER = 'chris123'
NEW_PASSWORD = 'chris123'

try:
    # Connect to MySQL as root
    print(f"Connecting to MySQL server at {DB_HOST} as {DB_USER}...")
    connection = pymysql.connect(
        host=DB_HOST,
        user=DB_USER,
        password=DB_PASSWORD,
        charset='utf8mb4',
        cursorclass=pymysql.cursors.DictCursor
    )
    
    print("Connection successful!")
    
    try:
        with connection.cursor() as cursor:
            # Drop user if exists
            print(f"\nDropping user '{NEW_USER}' if exists...")
            try:
                cursor.execute(f"DROP USER IF EXISTS '{NEW_USER}'@'%'")
                print(f"User '{NEW_USER}' dropped (if existed).")
            except Exception as e:
                print(f"Note: {e}")
            
            # Create the user
            print(f"\nCreating user '{NEW_USER}'...")
            cursor.execute(f"CREATE USER '{NEW_USER}'@'%' IDENTIFIED BY '{NEW_PASSWORD}'")
            print(f"User '{NEW_USER}' created successfully.")
            
            # Grant permissions
            print(f"\nGranting permissions on {DB_NAME}.{TABLE_NAME}...")
            cursor.execute(
                f"GRANT SELECT, INSERT, UPDATE, DELETE ON {DB_NAME}.{TABLE_NAME} TO '{NEW_USER}'@'%'"
            )
            print(f"Permissions granted successfully.")
            
            # Flush privileges
            print("\nFlushing privileges...")
            cursor.execute("FLUSH PRIVILEGES")
            print("Privileges flushed.")
            
            # Verify grants
            print(f"\nVerifying grants for '{NEW_USER}'...")
            cursor.execute(f"SHOW GRANTS FOR '{NEW_USER}'@'%'")
            grants = cursor.fetchall()
            
            print("\n" + "="*60)
            print("GRANT VERIFICATION:")
            print("="*60)
            for grant in grants:
                print(grant[f"Grants for {NEW_USER}@%"])
            print("="*60)
            
            print(f"\n✓ User '{NEW_USER}' created successfully!")
            print(f"✓ Permissions: SELECT, INSERT, UPDATE, DELETE on {DB_NAME}.{TABLE_NAME}")
            print(f"\nYou can now connect using:")
            print(f"  mysql -h {DB_HOST} -u {NEW_USER} -p{NEW_PASSWORD} {DB_NAME}")
            
    finally:
        connection.close()
        print("\nConnection closed.")

except pymysql.Error as e:
    print(f"\n✗ MySQL Error: {e}")
    sys.exit(1)
except Exception as e:
    print(f"\n✗ Error: {e}")
    sys.exit(1)
