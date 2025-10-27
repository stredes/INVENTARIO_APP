PYTEST?=pytest
RUFF?=ruff
BLACK?=black
ISORT?=isort
MYPY?=mypy
BANDIT?=bandit
PIP_AUDIT?=pip-audit

.PHONY: check lint types test cover security format precommit-install

check: lint types test security ## Run all: lint+types+tests+coverage+security

lint: ## Ruff + Black check + isort check
	$(RUFF) check .
	$(BLACK) --check --line-length 100 .
	$(ISORT) --check-only --profile black --line-length 100 .

types: ## mypy type-check
	$(MYPY) --ignore-missing-imports src scripts

test: ## pytest with coverage
	$(PYTEST) -q --cov=src --cov-report=term-missing --cov-report=xml

security: ## bandit + pip-audit (best-effort)
	-$(BANDIT) -q -r src
	-$(PIP_AUDIT) -r requirements.txt || echo "pip-audit not available or failed; continuing"

format: ## Apply Ruff fixes + Black + isort
	$(RUFF) check --fix .
	$(ISORT) --profile black --line-length 100 .
	$(BLACK) --line-length 100 .

precommit-install:
	pre-commit install
	pre-commit autoupdate || true

