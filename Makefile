.PHONY: up down test backend-test gateway-test admin-test mobile-test

up:
	docker compose up --build

down:
	docker compose down

test:
	powershell -ExecutionPolicy Bypass -File scripts/test_all.ps1

backend-test:
	cd backend && python -m pytest

gateway-test:
	cd drone_gateway && python -m pytest

admin-test:
	cd admin_web && npm run test

mobile-test:
	cd mobile && flutter test
