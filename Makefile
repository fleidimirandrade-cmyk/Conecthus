.PHONY: up down logs migrate importar-deputados importar-ceap test test-backend test-frontend

up:            ## Sobe db, backend e frontend
	docker compose up -d --build

down:          ## Para os containers (preserva volumes/dados)
	docker compose down

logs:
	docker compose logs -f backend

migrate:
	docker compose exec backend alembic upgrade head

importar-deputados:
	docker compose exec backend python -m app.cli deputados

importar-ceap: ## Uso: make importar-ceap ANO=2024
	docker compose exec backend python -m app.cli ceap --ano $(ANO)

test: test-backend test-frontend

test-backend:
	cd backend && pytest -q

test-frontend:
	cd frontend && npm test && npm run typecheck
