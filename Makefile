# All targets run through the project virtualenv created by ./setup.sh.
# Override to use another interpreter, e.g.:
#   make PYTHON=$(shell command -v python3)
PYTHON ?= .venv/bin/python

.DEFAULT_GOAL := default

.PHONY: all clean default setup prune

# Guard: fail with a helpful message when the venv interpreter is missing.
# (Works because make treats $(PYTHON) as a file target; overrides must be a path.)
$(PYTHON):
	@echo "Virtualenv not found at $(PYTHON). Run ./setup.sh to create it." >&2
	@exit 1

default: $(PYTHON)
	$(PYTHON) make.py

setup: $(PYTHON)
	$(PYTHON) make.py setup

prune: $(PYTHON)
	$(PYTHON) make.py prune

clean:
	rm -f .file_hashes.json .slug_uuid_mapping.json

all: clean default
