# Tasks: Empaquetado Linux — Fase A

Spec: `docs/specs/packaging-install-desktop-2026-09-13.md`  
Rama: `feat/packaging-fase-a-install-desktop`

## Task 1: Resolución de paths (XDG / app root)

- [x] Helpers `resolve_app_root`, `resolve_config_dir`, `resolve_config_path`, `resolve_example_config_path`
- [x] `AppController` usa esos helpers (no `Path.cwd()` a ciegas para config)
- [x] `_shipped_defaults` / example respetan `WLCL_APP_ROOT`
- [x] Tests unitarios con env + `tmp_path`
- [x] Verify: `pytest -q tests/test_packaging_paths.py` (+ config)

## Task 2: Assets packaging + scripts install/uninstall

- [x] `packaging/whisper-live-captions.desktop.in`
- [x] `packaging/icons/whisper-live-captions.svg`
- [x] `scripts/install-user.sh` / `scripts/uninstall-user.sh` (idempotentes, sin sudo)
- [x] Wrapper generado con PyQt6 env como `run.sh`
- [x] Verify: smoke install en `HOME` temporal

## Task 3: Make + README

- [x] Targets `install-user` / `uninstall-user` (`PURGE_CONFIG`)
- [x] README: sección instalación usuario + nota Fase B planificada
- [x] Verify: tests paths + `make lint`

## Task 4: Smoke manual (acceptance)

- [ ] `make install-user` → aparece en menú → arranca
- [ ] Guardar Settings → relanzar desde menú → persiste (XDG)
- [ ] `make run` en repo sigue con `config.json` local
- [ ] `make uninstall-user` quita icono; config XDG permanece
- [ ] `PURGE_CONFIG=1` borra config

## Fuera de esta rama (Fase B)

- [ ] `packaging/build-deb.sh` + metadata nfpm/dpkg
- [ ] Layout `/opt` + `/usr/share/applications`
- [ ] Release GitHub con `.deb`
- [ ] Texto licencias NC en paquete
