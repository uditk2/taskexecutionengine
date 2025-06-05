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

# Wait for database to be ready
wait_for_db

# Run database migrations with proper error handling
echo "Running database migrations..."

echo "Running task outputs migration..."
if ! python migrate_task_outputs.py; then
    echo "❌ Task outputs migration failed!"
    exit 1
fi

echo "Running workflow scheduling migration..."
if ! python migrate_workflow_scheduling.py; then
    echo "❌ Workflow scheduling migration failed!"
    exit 1
fi

echo "✅ All migrations completed successfully."

# Execute the main command
exec "$@"