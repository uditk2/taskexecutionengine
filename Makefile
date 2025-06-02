.PHONY: help build up down logs clean test lint format

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

clean: ## Clean up containers, networks, and volumes
	docker-compose down -v --remove-orphans
	docker system prune -f

test: ## Run tests
	docker-compose exec web pytest

lint: ## Run linting
	docker-compose exec web flake8 app/

format: ## Format code
	docker-compose exec web black app/

dev-setup: ## Set up development environment
	cp .env.example .env
	docker-compose up -d postgres redis
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

scale-workers: ## Scale workers (usage: make scale-workers WORKERS=4)
	docker-compose up -d --scale worker=$(WORKERS)