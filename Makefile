.PHONY: install up down test benchmark simulate-happy-path logs

install:
	pip install -e invariant-shared/
	pip install -e order-service/
	pip install -e payment-service/
	pip install -e erp-service/
	pip install -e shipping-service/
	pip install -e simulator/
	pip install -e failure-generator/
	pip install -e invariant-core/
	pip install -e invariant-ai/
	pip install -e invariant-recovery/

up:
	docker-compose up -d

down:
	docker-compose down

test:
	@echo "=== Running Simulator Tests ==="
	cd simulator && PYTHONPATH=. pytest tests/ -v
	@echo "=== Running Failure Generator Tests ==="
	cd failure-generator && PYTHONPATH=. pytest tests/ -v
	@echo "=== Running Invariant Core Tests ==="
	cd invariant-core && PYTHONPATH=. pytest tests/ -v
	@echo "=== Running Invariant AI Tests ==="
	cd invariant-ai && PYTHONPATH=. pytest tests/ -v
	@echo "=== Running Invariant Recovery Tests ==="
	cd invariant-recovery && PYTHONPATH=. pytest tests/ -v

benchmark:
	python3 benchmark/benchmark_runner.py

simulate-happy-path:
	curl -s -X POST http://localhost:8000/simulate/happy_path | python3 -m json.tool

logs:
	docker-compose logs -f
