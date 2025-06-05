"""
Database migration to add workflow scheduling columns
Run this script to update existing database schema for workflow scheduling functionality
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from sqlalchemy import text
from app.core.database import engine

def migrate_database():
    """Add scheduling-related columns to workflows table"""
    print("🔄 Starting workflow scheduling migration...")
    
    try:
        # Test database connection first
        with engine.connect() as test_conn:
            test_conn.execute(text("SELECT 1"))
            print("✅ Database connection verified")
    except Exception as e:
        print(f"❌ Cannot connect to database: {e}")
        sys.exit(1)
    
    # Use a transaction to ensure atomicity
    with engine.begin() as conn:
        try:
            # Verify workflows table exists
            result = conn.execute(text("""
                SELECT table_name FROM information_schema.tables 
                WHERE table_name = 'workflows' AND table_schema = 'public'
            """))
            if not result.fetchone():
                print("❌ Workflows table does not exist!")
                sys.exit(1)
            
            print("✅ Workflows table found")
            
            # List of columns to add with their definitions
            columns_to_add = [
                {
                    'name': 'is_scheduled',
                    'definition': 'is_scheduled BOOLEAN DEFAULT FALSE NOT NULL',
                    'description': 'Whether the workflow is scheduled'
                },
                {
                    'name': 'cron_expression',
                    'definition': 'cron_expression VARCHAR(255)',
                    'description': 'Cron expression for scheduling'
                },
                {
                    'name': 'timezone',
                    'definition': 'timezone VARCHAR(100) DEFAULT \'UTC\'',
                    'description': 'Timezone for scheduling'
                },
                {
                    'name': 'next_run_at',
                    'definition': 'next_run_at TIMESTAMP WITH TIME ZONE',
                    'description': 'Next scheduled run time'
                },
                {
                    'name': 'last_run_at',
                    'definition': 'last_run_at TIMESTAMP WITH TIME ZONE',
                    'description': 'Last run time'
                },
                {
                    'name': 'run_count',
                    'definition': 'run_count INTEGER DEFAULT 0 NOT NULL',
                    'description': 'Number of times workflow has been executed'
                }
            ]
            
            added_columns = 0
            for column in columns_to_add:
                # Check if column already exists
                result = conn.execute(text("""
                    SELECT column_name FROM information_schema.columns 
                    WHERE table_name = 'workflows' AND column_name = :column_name
                """), {"column_name": column['name']})
                
                if not result.fetchone():
                    # Add the new column
                    print(f"🔄 Adding column {column['name']}...")
                    conn.execute(text(f"""
                        ALTER TABLE workflows ADD COLUMN {column['definition']}
                    """))
                    
                    # Verify the column was added
                    verify_result = conn.execute(text("""
                        SELECT column_name FROM information_schema.columns 
                        WHERE table_name = 'workflows' AND column_name = :column_name
                    """), {"column_name": column['name']})
                    
                    if verify_result.fetchone():
                        print(f"✅ Added {column['name']} column - {column['description']}")
                        added_columns += 1
                    else:
                        print(f"❌ Failed to add {column['name']} column")
                        raise Exception(f"Column {column['name']} was not created successfully")
                else:
                    print(f"✅ {column['name']} column already exists")
            
            # Create index on is_scheduled for better query performance
            try:
                # Check if index already exists
                index_result = conn.execute(text("""
                    SELECT indexname FROM pg_indexes 
                    WHERE tablename = 'workflows' AND indexname = 'idx_workflows_is_scheduled'
                """))
                
                if not index_result.fetchone():
                    print("🔄 Creating index on is_scheduled column...")
                    conn.execute(text("""
                        CREATE INDEX idx_workflows_is_scheduled 
                        ON workflows (is_scheduled)
                    """))
                    print("✅ Created index on is_scheduled column")
                else:
                    print("✅ Index on is_scheduled column already exists")
            except Exception as e:
                print(f"⚠️ Index creation warning: {e}")
            
            # Final verification: check all columns exist
            print("🔄 Verifying all columns were created...")
            for column in columns_to_add:
                result = conn.execute(text("""
                    SELECT column_name FROM information_schema.columns 
                    WHERE table_name = 'workflows' AND column_name = :column_name
                """), {"column_name": column['name']})
                
                if not result.fetchone():
                    raise Exception(f"Verification failed: Column {column['name']} does not exist after migration")
            
            print(f"✅ Workflow scheduling migration completed successfully! Added {added_columns} new columns.")
                
        except Exception as e:
            print(f"❌ Migration failed: {e}")
            raise

if __name__ == "__main__":
    migrate_database()