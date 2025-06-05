.PHONY: help build up down logs clean test lint format setup-notifications

help: ## Show this help message
	@echo 'Usage: make [target]'
	@echo ''
	@echo 'Targets:'
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "  %-15s %s\n", $$1, $$2}' $(MAKEFILE_LIST)

build: ## Build all Docker images
	docker-compose build

up: ## Start all services
	docker-compose up -d

down: ## Stop all services
	docker-compose down

logs: ## Show logs from all services
	docker-compose logs -f

logs-web: ## Show logs from web service only
	docker-compose logs -f web

logs-worker: ## Show logs from worker service only
	docker-compose logs -f worker

logs-migrations: ## Show migration logs during startup
	docker-compose logs web | grep -E "(migration|Migration|🔄|✅|❌)"

clean: ## Clean up containers, networks, and volumes
	docker-compose down -v --remove-orphans
	docker system prune -f

test: ## Run tests
	docker-compose exec web pytest

lint: ## Run linting
	docker-compose exec web flake8 app/

format: ## Format code
	docker-compose exec web black app/

setup-notifications: ## Set up notification configuration for Docker
	@echo "Setting up notification configuration..."
	@if [ ! -f .env ]; then \
		cp .env.docker.example .env; \
		echo "✅ Created .env file from .env.docker.example"; \
		echo "📝 Please edit .env file to configure your notification providers"; \
		echo "   - Uncomment and set SMTP_USERNAME, SMTP_PASSWORD for email"; \
		echo "   - Uncomment and set TWILIO_* variables for SMS"; \
		echo "   - Uncomment and set TELEGRAM_BOT_TOKEN for Telegram"; \
		echo "   - Set default notification recipients"; \
	else \
		echo "⚠️  .env file already exists. Check .env.docker.example for notification settings"; \
	fi

check-notifications: ## Check notification system status
	@echo "Checking notification system status..."
	curl -s http://localhost:8000/api/v1/notifications/status | python -m json.tool || echo "❌ Could not connect to notification API"

test-notifications: ## Send test notifications
	@echo "Sending test email notification..."
	curl -X POST "http://localhost:8000/api/v1/notifications/test" \
		-H "Content-Type: application/json" \
		-d '{"notification_type": "email", "recipient": "test@example.com", "message": "Test notification from Docker"}' \
		| python -m json.tool || echo "❌ Failed to send test notification"

dev-setup: ## Set up development environment
	cp .env.notifications.example .env
	docker-compose up -d db redis
	pip install -r requirements.txt

dev-run: ## Run development server
	uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

dev-worker: ## Run development Celery worker
	celery -A app.celery_app worker --loglevel=info

dev-beat: ## Run development Celery beat
	celery -A app.celery_app beat --loglevel=info

status: ## Show status of all services
	docker-compose ps

restart: ## Restart all services
	docker-compose restart

restart-web: ## Restart web service only
	docker-compose restart web

restart-worker: ## Restart worker service only
	docker-compose restart worker

scale-workers: ## Scale workers (usage: make scale-workers WORKERS=4)
	docker-compose up -d --scale worker=$(WORKERS)

shell-web: ## Open shell in web container
	docker-compose exec web bash

shell-worker: ## Open shell in worker container
	docker-compose exec worker bash

db-shell: ## Open database shell
	docker-compose exec db psql -U postgres -d task_engine

redis-shell: ## Open Redis shell
	docker-compose exec redis redis-cli

deploy: ## Full deployment setup with notifications
	@echo "🚀 Deploying Task Execution Engine with Notification System..."
	@make setup-notifications
	@echo "📦 Building Docker images..."
	@make build
	@echo "🔄 Starting services..."
	@make up
	@echo "⏳ Waiting for services to be ready..."
	@sleep 30
	@echo "✅ Deployment complete!"
	@echo ""
	@echo "🔧 Next steps:"
	@echo "   1. Edit .env file to configure notification providers"
	@echo "   2. Restart services: make restart"
	@echo "   3. Check status: make check-notifications"
	@echo "   4. Test notifications: make test-notifications"
	@echo ""
	@echo "📊 Service URLs:"
	@echo "   - Web UI: http://localhost:8000"
	@echo "   - API Docs: http://localhost:8000/docs"
	@echo "   - Flower (Celery): http://localhost:5555"
	@echo "   - Notification Status: http://localhost:8000/api/v1/notifications/status"