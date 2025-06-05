#!/usr/bin/env python3
"""
Comprehensive database migration script for Task Execution Engine
Run this script to set up or update the complete database schema
"""

import sys
import os
import subprocess
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent
sys.path.append(str(project_root))

def run_migration_script(script_name: str, description: str):
    """Run a migration script and handle errors"""
    print(f"\n{'='*60}")
    print(f"📦 {description}")
    print(f"{'='*60}")
    
    script_path = project_root / script_name
    
    if not script_path.exists():
        print(f"❌ Migration script not found: {script_path}")
        return False
    
    try:
        # Run the migration script
        result = subprocess.run([
            sys.executable, str(script_path)
        ], capture_output=True, text=True, cwd=project_root)
        
        if result.returncode == 0:
            print(result.stdout)
            print(f"✅ {description} completed successfully")
            return True
        else:
            print(f"❌ {description} failed:")
            print(result.stdout)
            print(result.stderr)
            return False
            
    except Exception as e:
        print(f"❌ Error running {script_name}: {e}")
        return False

def check_database_connection():
    """Check if database is available"""
    print("🔄 Testing database connection...")
    try:
        from app.core.database import engine
        from sqlalchemy import text
        
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        print("✅ Database connection successful")
        return True
    except Exception as e:
        print(f"❌ Database connection failed: {e}")
        print("\n💡 Make sure:")
        print("   - PostgreSQL is running")
        print("   - Database credentials in .env are correct")
        print("   - Database exists")
        return False

def main():
    """Run all database migrations in order"""
    print("🚀 Starting Task Execution Engine Database Migration")
    print("=" * 60)
    
    # Check database connection first
    if not check_database_connection():
        print("\n❌ Cannot proceed without database connection")
        sys.exit(1)
    
    # List of migrations to run in order
    migrations = [
        {
            "script": "migrate_task_outputs.py",
            "description": "Task Outputs Migration - Add task_outputs column"
        },
        {
            "script": "migrate_workflow_scheduling.py", 
            "description": "Workflow Scheduling Migration - Add scheduling columns"
        },
        {
            "script": "migrate_notifications.py",
            "description": "Notification System Migration - Add notification tables"
        }
    ]
    
    successful_migrations = 0
    total_migrations = len(migrations)
    
    for migration in migrations:
        success = run_migration_script(
            migration["script"],
            migration["description"]
        )
        
        if success:
            successful_migrations += 1
        else:
            print(f"\n❌ Migration failed: {migration['description']}")
            print("🛑 Stopping migration process due to error")
            sys.exit(1)
    
    # Summary
    print(f"\n{'='*60}")
    print("🎉 MIGRATION SUMMARY")
    print(f"{'='*60}")
    print(f"✅ Successfully completed {successful_migrations}/{total_migrations} migrations")
    
    if successful_migrations == total_migrations:
        print("\n🎯 All migrations completed successfully!")
        print("\n🔧 Next steps:")
        print("   1. Configure notification providers in .env file")
        print("   2. Start the application: python -m app.main")
        print("   3. Start Celery worker: celery -A app.celery_app worker --loglevel=info")
        print("   4. Test notifications: GET /api/v1/notifications/status")
        print("\n📚 Documentation:")
        print("   - Notification setup: NOTIFICATIONS.md")
        print("   - Environment config: .env.notifications.example")
    else:
        print(f"\n❌ {total_migrations - successful_migrations} migrations failed")
        sys.exit(1)

if __name__ == "__main__":
    main()