#!/bin/sh

# This entrypoint script initializes services when the container starts.

echo "Starting Task Execution Engine..."

# Function to wait for database to be ready
wait_for_db() {
    echo "Waiting for database to be ready..."
    max_attempts=30
    attempt=1
    
    while [ $attempt -le $max_attempts ]; do
        echo "Database connection attempt $attempt/$max_attempts..."
        
        # Try to connect to database using Python
        python -c "
import sys
import os
sys.path.append('/app')
try:
    from sqlalchemy import text
    from app.core.database import engine
    with engine.connect() as conn:
        result = conn.execute(text('SELECT 1'))
        print('Database connection successful!')
    sys.exit(0)
except Exception as e:
    print(f'Database connection failed: {e}')
    sys.exit(1)
        " && break
        
        if [ $attempt -eq $max_attempts ]; then
            echo "❌ Failed to connect to database after $max_attempts attempts"
            exit 1
        fi
        
        echo "Database not ready, waiting 3 seconds..."
        sleep 3
        attempt=$((attempt + 1))
    done
    
    echo "✅ Database is ready!"
}

# Function to run a migration with error handling
run_migration() {
    local migration_script=$1
    local migration_name=$2
    
    echo "🔄 Running $migration_name..."
    if python "$migration_script"; then
        echo "✅ $migration_name completed successfully"
        return 0
    else
        echo "❌ $migration_name failed!"
        return 1
    fi
}

# Wait for database to be ready
wait_for_db

# Run all database migrations in the correct order
echo "🚀 Starting database migrations..."

# 1. Task outputs migration
if ! run_migration "migrate_task_outputs.py" "Task Outputs Migration"; then
    exit 1
fi

# 2. Workflow scheduling migration
if ! run_migration "migrate_workflow_scheduling.py" "Workflow Scheduling Migration"; then
    exit 1
fi

# 3. Notification system migration
if ! run_migration "migrate_notifications.py" "Notification System Migration"; then
    exit 1
fi

echo "🎉 All database migrations completed successfully!"

# Initialize database tables if this is the first run
echo "🔄 Initializing database tables..."
python -c "
import sys
sys.path.append('/app')
try:
    from app.core.database import init_db
    init_db()
    print('✅ Database tables initialized successfully')
except Exception as e:
    print(f'⚠️ Database initialization warning: {e}')
    # Don't exit on initialization warnings as tables might already exist
"

echo "✅ Task Execution Engine initialization complete!"

# Execute the main command
exec "$@"