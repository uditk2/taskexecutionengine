"""
Database migration to add notification system tables and columns
Run this script to update existing database schema for notification functionality
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from sqlalchemy import text
from app.core.database import engine

def migrate_database():
    """Add notification-related tables and columns"""
    print("🔄 Starting notification system migration...")
    
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
            print("🔄 Creating notification_configs table...")
            
            # Create notification_configs table if it doesn't exist
            table_check = conn.execute(text("""
                SELECT table_name FROM information_schema.tables 
                WHERE table_name = 'notification_configs' AND table_schema = 'public'
            """))
            
            if not table_check.fetchone():
                conn.execute(text("""
                    CREATE TABLE notification_configs (
                        id SERIAL PRIMARY KEY,
                        user_id VARCHAR(255),
                        workflow_id INTEGER REFERENCES workflows(id) ON DELETE CASCADE,
                        task_id INTEGER REFERENCES tasks(id) ON DELETE CASCADE,
                        
                        -- Notification types enabled
                        email_enabled BOOLEAN DEFAULT FALSE NOT NULL,
                        sms_enabled BOOLEAN DEFAULT FALSE NOT NULL,
                        telegram_enabled BOOLEAN DEFAULT FALSE NOT NULL,
                        desktop_enabled BOOLEAN DEFAULT TRUE NOT NULL,
                        
                        -- Contact details
                        email_address VARCHAR(255),
                        phone_number VARCHAR(20),
                        telegram_chat_id VARCHAR(255),
                        
                        -- Event filters (stored as JSON array)
                        events JSON DEFAULT '[]'::json,
                        priority_filter VARCHAR(20) DEFAULT 'normal' NOT NULL,
                        
                        -- Notification settings
                        quiet_hours_start TIME,
                        quiet_hours_end TIME,
                        timezone VARCHAR(100) DEFAULT 'UTC' NOT NULL,
                        
                        -- Timestamps
                        created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                        
                        -- Constraints
                        CONSTRAINT check_priority_filter CHECK (priority_filter IN ('low', 'normal', 'high', 'urgent')),
                        CONSTRAINT check_at_least_one_contact CHECK (
                            email_address IS NOT NULL OR 
                            phone_number IS NOT NULL OR 
                            telegram_chat_id IS NOT NULL OR
                            desktop_enabled = TRUE
                        )
                    )
                """))
                print("✅ Created notification_configs table")
            else:
                print("✅ notification_configs table already exists")
            
            print("🔄 Creating notification_history table...")
            
            # Create notification_history table if it doesn't exist
            history_check = conn.execute(text("""
                SELECT table_name FROM information_schema.tables 
                WHERE table_name = 'notification_history' AND table_schema = 'public'
            """))
            
            if not history_check.fetchone():
                conn.execute(text("""
                    CREATE TABLE notification_history (
                        id SERIAL PRIMARY KEY,
                        workflow_id INTEGER REFERENCES workflows(id) ON DELETE CASCADE,
                        task_id INTEGER REFERENCES tasks(id) ON DELETE CASCADE,
                        
                        -- Notification details
                        event VARCHAR(50) NOT NULL,
                        provider VARCHAR(50) NOT NULL,
                        recipient VARCHAR(255) NOT NULL,
                        title VARCHAR(255) NOT NULL,
                        message TEXT,
                        priority VARCHAR(20) DEFAULT 'normal' NOT NULL,
                        
                        -- Result details
                        success BOOLEAN NOT NULL,
                        error_message TEXT,
                        provider_message_id VARCHAR(255),
                        
                        -- Metadata
                        metadata JSON DEFAULT '{}'::json,
                        
                        -- Timestamps
                        sent_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                        
                        -- Constraints
                        CONSTRAINT check_event CHECK (event IN (
                            'task_started', 'task_completed', 'task_failed',
                            'workflow_started', 'workflow_completed', 'workflow_failed', 'workflow_scheduled'
                        )),
                        CONSTRAINT check_priority CHECK (priority IN ('low', 'normal', 'high', 'urgent')),
                        CONSTRAINT check_provider CHECK (provider IN ('email', 'sms', 'telegram', 'desktop'))
                    )
                """))
                print("✅ Created notification_history table")
            else:
                print("✅ notification_history table already exists")
            
            print("🔄 Creating indexes for better performance...")
            
            # Create indexes for better query performance
            indexes_to_create = [
                {
                    'name': 'idx_notification_configs_workflow_id',
                    'sql': 'CREATE INDEX idx_notification_configs_workflow_id ON notification_configs (workflow_id)',
                    'description': 'Index on workflow_id for notification configs'
                },
                {
                    'name': 'idx_notification_configs_task_id',
                    'sql': 'CREATE INDEX idx_notification_configs_task_id ON notification_configs (task_id)',
                    'description': 'Index on task_id for notification configs'
                },
                {
                    'name': 'idx_notification_configs_user_id',
                    'sql': 'CREATE INDEX idx_notification_configs_user_id ON notification_configs (user_id)',
                    'description': 'Index on user_id for notification configs'
                },
                {
                    'name': 'idx_notification_history_workflow_id',
                    'sql': 'CREATE INDEX idx_notification_history_workflow_id ON notification_history (workflow_id)',
                    'description': 'Index on workflow_id for notification history'
                },
                {
                    'name': 'idx_notification_history_task_id',
                    'sql': 'CREATE INDEX idx_notification_history_task_id ON notification_history (task_id)',
                    'description': 'Index on task_id for notification history'
                },
                {
                    'name': 'idx_notification_history_sent_at',
                    'sql': 'CREATE INDEX idx_notification_history_sent_at ON notification_history (sent_at)',
                    'description': 'Index on sent_at for notification history'
                },
                {
                    'name': 'idx_notification_history_event_success',
                    'sql': 'CREATE INDEX idx_notification_history_event_success ON notification_history (event, success)',
                    'description': 'Composite index on event and success'
                }
            ]
            
            created_indexes = 0
            for index in indexes_to_create:
                try:
                    # Check if index already exists
                    index_result = conn.execute(text("""
                        SELECT indexname FROM pg_indexes 
                        WHERE indexname = :index_name
                    """), {"index_name": index['name']})
                    
                    if not index_result.fetchone():
                        conn.execute(text(index['sql']))
                        print(f"✅ Created {index['name']} - {index['description']}")
                        created_indexes += 1
                    else:
                        print(f"✅ {index['name']} already exists")
                except Exception as e:
                    print(f"⚠️ Index creation warning for {index['name']}: {e}")
            
            print("🔄 Creating sample notification configuration...")
            
            # Create a default notification configuration if none exists
            existing_config = conn.execute(text("""
                SELECT id FROM notification_configs LIMIT 1
            """))
            
            if not existing_config.fetchone():
                # Insert a default configuration that can be customized
                conn.execute(text("""
                    INSERT INTO notification_configs (
                        user_id, workflow_id, task_id,
                        email_enabled, sms_enabled, telegram_enabled, desktop_enabled,
                        events, priority_filter, timezone
                    ) VALUES (
                        'default', NULL, NULL,
                        FALSE, FALSE, FALSE, TRUE,
                        '["task_completed", "task_failed", "workflow_completed", "workflow_failed"]'::json,
                        'normal', 'UTC'
                    )
                """))
                print("✅ Created default notification configuration")
            else:
                print("✅ Notification configurations already exist")
            
            # Final verification: check all tables exist
            print("🔄 Verifying notification tables were created...")
            
            tables_to_verify = ['notification_configs', 'notification_history']
            for table_name in tables_to_verify:
                result = conn.execute(text("""
                    SELECT table_name FROM information_schema.tables 
                    WHERE table_name = :table_name AND table_schema = 'public'
                """), {"table_name": table_name})
                
                if not result.fetchone():
                    raise Exception(f"Verification failed: Table {table_name} does not exist after migration")
            
            print(f"✅ Notification system migration completed successfully!")
            print(f"   - Created notification_configs table")
            print(f"   - Created notification_history table") 
            print(f"   - Created {created_indexes} performance indexes")
            print(f"   - Added default configuration")
            print("")
            print("🔧 Next steps:")
            print("   1. Configure notification providers in .env file")
            print("   2. Customize notification settings via API or database")
            print("   3. Test notifications using /api/v1/notifications/test endpoint")
                
        except Exception as e:
            print(f"❌ Migration failed: {e}")
            raise

if __name__ == "__main__":
    migrate_database()