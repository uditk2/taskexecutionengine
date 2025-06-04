"""
Simple database migration to add task_outputs column
Run this script to update existing database schema
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from sqlalchemy import text
from app.core.database import engine

def migrate_database():
    """Add task_outputs column to tasks table"""
    with engine.connect() as conn:
        try:
            # Check if column already exists
            result = conn.execute(text("""
                SELECT column_name FROM information_schema.columns 
                WHERE table_name = 'tasks' AND column_name = 'task_outputs'
            """))
            
            if not result.fetchone():
                # Add the new column
                conn.execute(text("""
                    ALTER TABLE tasks ADD COLUMN task_outputs JSON DEFAULT '{}'::json
                """))
                conn.commit()
                print("✅ Added task_outputs column to tasks table")
            else:
                print("✅ task_outputs column already exists")
                
        except Exception as e:
            print(f"❌ Migration failed: {e}")
            conn.rollback()
            raise

if __name__ == "__main__":
    migrate_database()