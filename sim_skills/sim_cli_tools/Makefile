PREFIX ?= $(HOME)/.local
BIN_DIR ?= $(PREFIX)/bin
PYTHON_BIN ?= /data/conda/envs/lbk/bin/python3
TOOL_ROOT := $(abspath .)

.PHONY: install-local
install-local:
	@mkdir -p "$(BIN_DIR)"
	@printf '%s\n' '#!/usr/bin/env bash' \
		'set -euo pipefail' \
		'exec "$(PYTHON_BIN)" "$(TOOL_ROOT)/sim_run.py" "$$@"' \
		> "$(BIN_DIR)/sim-run"
	@chmod +x "$(BIN_DIR)/sim-run"
	@rm -f "$(BIN_DIR)/sim-run-03-06"
	@printf 'installed %s\n' "$(BIN_DIR)/sim-run"
