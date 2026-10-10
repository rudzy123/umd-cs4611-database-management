PYTHON ?= python3
export DATABASE_URL ?= postgresql://library:library@localhost:5432/library

.PHONY: up down reset install migrate seed test explain check psql

up:
	docker compose up -d --wait

down:
	docker compose down

reset:
	docker compose down -v
	docker compose up -d --wait
	$(PYTHON) -m library.migrate
	$(PYTHON) -m library.seed

install:
	$(PYTHON) -m pip install -e ".[dev]"

migrate:
	$(PYTHON) -m library.migrate

seed:
	$(PYTHON) -m library.seed

test:
	$(PYTHON) -m pytest

explain:
	$(PYTHON) -m library.explain

check: migrate seed test explain

psql:
	docker compose exec db psql -U library -d library
