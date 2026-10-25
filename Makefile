.PHONY: install migrate run seed test test-pg lint docker-up docker-down

install:            ## runtime + test + lint dependencies
	python -m pip install -r requirements-dev.txt

migrate:            ## apply database migrations (uses DATABASE_URL / .env)
	alembic upgrade head

run:                ## start the API with auto-reload on http://localhost:8000
	uvicorn app.main:app --reload

seed:               ## optional demo data
	python -m scripts.seed

test:               ## whole suite on in-memory SQLite
	pytest -q

test-pg:            ## whole suite on PostgreSQL; set TEST_DATABASE_URL first
	pytest -q

lint:
	ruff check .

docker-up:
	docker compose up --build

docker-down:
	docker compose down
