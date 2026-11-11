PYTHON ?= python3
FIXTURE ?= fixture

.PHONY: install lint test experiments receipts verify lint-fixture evidence clean

install:
	$(PYTHON) -m pip install -e ".[dev]"

lint:
	$(PYTHON) -m ruff check .
	$(PYTHON) -m ruff format --check .

test:
	$(PYTHON) -m pytest --junitxml=reports/junit.xml --cov=afcl --cov-branch \
		--cov-report=json:reports/coverage.json --cov-report=term-missing

lint-fixture:
	$(PYTHON) -m afcl lint $(FIXTURE); test $$? -eq 1

experiments:
	$(PYTHON) experiments/exp01_drift_census.py
	$(PYTHON) experiments/exp02_name_only_review.py
	$(PYTHON) experiments/exp03_undecidable.py
	$(PYTHON) experiments/exp04_severity_evidence.py

receipts:
	$(PYTHON) tools/collect_metrics.py --skip-tests
	$(PYTHON) tools/check_numbers.py

verify: lint test experiments receipts

evidence:
	$(PYTHON) tools/render_architecture.py
	$(PYTHON) tools/capture_screenshots.py
	$(PYTHON) tools/record_demo.py

clean:
	rm -rf reports .pytest_cache .ruff_cache build dist src/*.egg-info
	find . -name __pycache__ -type d -prune -exec rm -rf {} +
