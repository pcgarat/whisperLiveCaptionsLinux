.PHONY: help venv install run test lint format clean devices config-init check

PYTHON ?= python3.12
VENV   := .venv
BIN    := $(VENV)/bin
export PYTHONPATH := $(CURDIR)

# Evita mezclar Qt del sistema (p. ej. Cursor) con el de PyQt6 del venv.
define PYQT_ENV
QT6_ROOT=$$($(BIN)/python -c 'import PyQt6, pathlib; print(pathlib.Path(PyQt6.__file__).resolve().parent / "Qt6")'); \
export LD_LIBRARY_PATH="$$QT6_ROOT/lib$${LD_LIBRARY_PATH:+:$$LD_LIBRARY_PATH}"; \
export QT_PLUGIN_PATH="$$QT6_ROOT/plugins"; \
export QT_QPA_PLATFORM="$${QT_QPA_PLATFORM:-xcb}"
endef

help: ## Muestra esta ayuda
	@awk 'BEGIN {FS = ":.*##"; printf "Targets:\n"} /^[a-zA-Z_-]+:.*?##/ {printf "  \033[36m%-14s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)

venv: ## Crea el entorno virtual (.venv)
	@test -d $(VENV) || $(PYTHON) -m venv $(VENV)
	$(BIN)/pip install -q -U pip

install: venv ## Instala dependencias de requirements.txt
	$(BIN)/pip install -q -r requirements.txt

run: install ## Arranca la app de subtítulos
	@$(PYQT_ENV); $(BIN)/python -m src.app

test: install ## Ejecuta tests unitarios (offscreen + libs Qt del venv)
	@QT6_ROOT="$$($(BIN)/python -c 'import PyQt6, pathlib; print(pathlib.Path(PyQt6.__file__).resolve().parent / "Qt6")')"; \
	export LD_LIBRARY_PATH="$$QT6_ROOT/lib$${LD_LIBRARY_PATH:+:$$LD_LIBRARY_PATH}"; \
	export QT_PLUGIN_PATH="$$QT6_ROOT/plugins"; \
	export QT_QPA_PLATFORM=offscreen; \
	$(BIN)/pytest -q

lint: install ## Lint con ruff
	$(BIN)/ruff check src tests

format: install ## Formatea con ruff
	$(BIN)/ruff check src tests --fix
	$(BIN)/ruff format src tests

check: test lint ## Tests + lint

devices: install ## Lista monitores PipeWire/Pulse disponibles
	$(BIN)/python -c "from src.audio.devices import list_audio_monitors; print('\n'.join(list_audio_monitors()) or '(ninguno)')"

config-init: ## Copia config.example.json → config.json si no existe
	@if [ -f config.json ]; then \
		echo "config.json ya existe"; \
	else \
		cp config.example.json config.json; \
		echo "Creado config.json"; \
	fi

clean: ## Borra caches y el venv
	rm -rf $(VENV) .pytest_cache .ruff_cache
	find . -type d -name '__pycache__' -prune -exec rm -rf {} +
