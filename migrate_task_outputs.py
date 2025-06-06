"""
Simple database migration to add task_outputs column
Run this script to update existing database schema
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from sqlalchemy import text
from app.core.database import engine, create_tables

def migrate_database():
    """Add task_outputs column to tasks table"""
    with engine.connect() as conn:
        try:
            # First check if tasks table exists
            result = conn.execute(text("""
                SELECT table_name FROM information_schema.tables 
                WHERE table_schema = 'public' AND table_name = 'tasks'
            """))
            
            if not result.fetchone():
                print("⚠️  Tasks table doesn't exist. Creating base database schema...")
                # Import models to ensure they're registered with Base
                from app.models.task import Task
                from app.models.workflow import Workflow
                try:
                    from app.notifications.models import NotificationTemplate, NotificationEvent
                except ImportError:
                    pass  # Notification models may not exist yet
                
                # Create all tables
                create_tables()
                print("✅ Base database schema created successfully")
                print("✅ task_outputs column is already included in the schema")
                return
            
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