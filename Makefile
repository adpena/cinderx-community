SHELL := /bin/sh
PNPM := corepack pnpm
SITE_DIR := packages/site
PY_DIR := python
UV := uv
PYTHON_VERSION ?= 3.14
VENV_DIR := .venv
VENV_STAMP := $(VENV_DIR)/.ready
SUMMARY_DIR := data/summary
STATIC_SUMMARY_DIR := packages/site/static/data/summary

.PHONY: dev fmt lint test build clean python-dev python-dev-cinderx cinderx-env-check cinderx-install-local cinderx-install-local-macos bench-toolchain bench-toolchain-compare bench-smoke-local bench-smoke-local-cinderx bench-pyperformance-local bench-pyperformance-local-cinderx bench-pyperformance-local-ci bench-pyperformance-local-cinderx-ci bench-publish-check bench-publish-check-smoke bench-dossier bench-dossier-smoke bench-run-quickstart-matrix bench-sync-site-data

$(VENV_STAMP): $(PY_DIR)/pyproject.toml
	$(UV) python install $(PYTHON_VERSION)
	$(UV) venv --python $(PYTHON_VERSION) --clear $(VENV_DIR)
	$(UV) pip install --python $(VENV_DIR)/bin/python -e ./$(PY_DIR)[dev]
	touch $(VENV_STAMP)

python-dev: $(VENV_STAMP)

python-dev-cinderx: $(VENV_STAMP)
	$(UV) pip install --python $(VENV_DIR)/bin/python -e ./$(PY_DIR)[dev,cinderx]

cinderx-env-check: python-dev
	@echo "workspace_python=$$($(VENV_DIR)/bin/python -c 'import sys; print(sys.executable)')"
	@echo "workspace_python_version=$$($(VENV_DIR)/bin/python -V)"
	@echo "cmake=$$(command -v cmake || echo missing)"
	@echo "clang=$$(command -v clang || echo missing)"
	@echo "ninja=$$(command -v ninja || echo missing)"
	@echo "CINDERX_PYTHON=$${CINDERX_PYTHON:-unset}"
	@$(VENV_DIR)/bin/python -c "import importlib.util; print('workspace_cinderx_importable=' + str(bool(importlib.util.find_spec('cinderx'))))"
	@if [ -n "$(CINDERX_PYTHON)" ]; then \
		"$(CINDERX_PYTHON)" -c "import importlib.util,sys; print('cinderx_python=' + sys.executable); print('cinderx_importable=' + str(bool(importlib.util.find_spec('cinderx'))))"; \
	fi

cinderx-install-local: python-dev
	$(UV) pip install --python $(VENV_DIR)/bin/python setuptools
	$(UV) pip install --python $(VENV_DIR)/bin/python --no-build-isolation cinderx

cinderx-install-local-macos: python-dev
	@if [ "$$(uname -s)" != "Darwin" ] || [ "$$(uname -m)" != "arm64" ]; then \
		echo "warning: macOS arm64 workaround target was requested on a non-macOS-arm64 host"; \
	fi
	CXXFLAGS='-include cstdlib' CMAKE_ARGS='-DCMAKE_VERBOSE_MAKEFILE:BOOL=ON' $(UV) pip install --python $(VENV_DIR)/bin/python -v --no-cache-dir --reinstall cinderx

bench-toolchain: python-dev
	$(UV) pip install --python $(VENV_DIR)/bin/python pyperformance

bench-toolchain-compare: python-dev
	bash scripts/bench/install_comparison_toolchain.sh

dev:
	$(PNPM) -C $(SITE_DIR) install
	$(PNPM) -C $(SITE_DIR) start --host 0.0.0.0 --port 3000

fmt: python-dev
	$(PNPM) -C $(SITE_DIR) install
	$(PNPM) -C $(SITE_DIR) format
	$(VENV_DIR)/bin/python -m ruff format $(PY_DIR)
	$(VENV_DIR)/bin/python -m ruff check --fix $(PY_DIR)

lint: python-dev
	$(PNPM) -C $(SITE_DIR) install
	$(PNPM) -C $(SITE_DIR) lint
	$(VENV_DIR)/bin/python -m ruff check $(PY_DIR)
	$(VENV_DIR)/bin/python -m ruff format --check $(PY_DIR)

test: python-dev
	$(VENV_DIR)/bin/python -m pytest $(PY_DIR)/cinderx_community/tests

build:
	$(PNPM) -C $(SITE_DIR) install
	$(PNPM) -C $(SITE_DIR) build

bench-smoke-local: python-dev
	cd $(PY_DIR) && ../$(VENV_DIR)/bin/cxc bench run --suite smoke --python ../$(VENV_DIR)/bin/python --ci-mode --out ../data/runs --summary-out ../$(SUMMARY_DIR) --static-summary-out ../$(STATIC_SUMMARY_DIR)

bench-smoke-local-cinderx: python-dev
	@if [ -z "$(CINDERX_PYTHON)" ]; then echo "Set CINDERX_PYTHON=/path/to/cinderx-python"; exit 2; fi
	cd $(PY_DIR) && ../$(VENV_DIR)/bin/cxc bench run --suite smoke --python ../$(VENV_DIR)/bin/python --cpython-cinderx "$(CINDERX_PYTHON)" --require-cinderx-baseline --out ../data/runs --summary-out ../$(SUMMARY_DIR) --static-summary-out ../$(STATIC_SUMMARY_DIR)

bench-pyperformance-local: bench-toolchain
	cd $(PY_DIR) && ../$(VENV_DIR)/bin/cxc bench run --suite pyperformance --python ../$(VENV_DIR)/bin/python --out ../data/runs --summary-out ../$(SUMMARY_DIR) --static-summary-out ../$(STATIC_SUMMARY_DIR)

bench-pyperformance-local-cinderx: bench-toolchain
	@if [ -z "$(CINDERX_PYTHON)" ]; then echo "Set CINDERX_PYTHON=/path/to/cinderx-python"; exit 2; fi
	cd $(PY_DIR) && ../$(VENV_DIR)/bin/cxc bench run --suite pyperformance --python ../$(VENV_DIR)/bin/python --cpython-cinderx "$(CINDERX_PYTHON)" --require-cinderx-baseline --out ../data/runs --summary-out ../$(SUMMARY_DIR) --static-summary-out ../$(STATIC_SUMMARY_DIR)

bench-pyperformance-local-ci: bench-toolchain
	cd $(PY_DIR) && ../$(VENV_DIR)/bin/cxc bench run --suite pyperformance --python ../$(VENV_DIR)/bin/python --ci-mode --out ../data/runs --summary-out ../$(SUMMARY_DIR) --static-summary-out ../$(STATIC_SUMMARY_DIR)

bench-pyperformance-local-cinderx-ci: bench-toolchain
	@if [ -z "$(CINDERX_PYTHON)" ]; then echo "Set CINDERX_PYTHON=/path/to/cinderx-python"; exit 2; fi
	cd $(PY_DIR) && ../$(VENV_DIR)/bin/cxc bench run --suite pyperformance --python ../$(VENV_DIR)/bin/python --cpython-cinderx "$(CINDERX_PYTHON)" --require-cinderx-baseline --ci-mode --out ../data/runs --summary-out ../$(SUMMARY_DIR) --static-summary-out ../$(STATIC_SUMMARY_DIR)

bench-publish-check: python-dev
	cd $(PY_DIR) && ../$(VENV_DIR)/bin/cxc bench verify-publish --summary-root ../$(SUMMARY_DIR) --static-summary-root ../$(STATIC_SUMMARY_DIR) --require-suite pyperformance

bench-publish-check-smoke: python-dev
	cd $(PY_DIR) && ../$(VENV_DIR)/bin/cxc bench verify-publish --summary-root ../$(SUMMARY_DIR) --static-summary-root ../$(STATIC_SUMMARY_DIR) --require-suite smoke

bench-dossier: python-dev
	cd $(PY_DIR) && ../$(VENV_DIR)/bin/cxc bench export-dossier --summary-root ../$(SUMMARY_DIR) --output-root ../$(SUMMARY_DIR)/reports --require-suite pyperformance

bench-dossier-smoke: python-dev
	cd $(PY_DIR) && ../$(VENV_DIR)/bin/cxc bench export-dossier --summary-root ../$(SUMMARY_DIR) --output-root ../$(SUMMARY_DIR)/reports --require-suite smoke

bench-run-quickstart-matrix: python-dev
	bash scripts/bench/run_quickstart_matrix.sh

bench-sync-site-data:
	bash scripts/bench/sync_site_data_from_bench_results.sh

clean:
	rm -rf $(SITE_DIR)/build $(SITE_DIR)/.docusaurus $(SITE_DIR)/.cache
	rm -rf $(PY_DIR)/.pytest_cache $(PY_DIR)/.ruff_cache
	rm -rf $(VENV_DIR)
	rm -rf .cache/upstream
