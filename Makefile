ENV = env
BIN = $(ENV)/bin
PYTHON = $(BIN)/python

clean:
	rm -rf $(ENV)
	rm -rf build
	rm -rf dist
	rm -rf *.egg
	rm -rf *.egg-info
	find | grep -i ".*\.pyc$$" | xargs -r -L1 rm

$(ENV):
	python3 -m venv $(ENV)
	$(PYTHON) -m pip install --upgrade pip setuptools wheel twine
	$(PYTHON) -m pip install -e .[dev]

develop: $(ENV)

install-ci: $(ENV)
	$(PYTHON) -m pip install --upgrade pip setuptools wheel twine build .

.PHONY: build
build:
	$(PYTHON) -m build
	$(BIN)/twine check dist/*

upload:
	$(BIN)/twine upload --skip-existing dist/*

build-vscode-extension:
	npm --prefix ./vscode/ run compile
	npm --prefix ./vscode/ run vsce-package