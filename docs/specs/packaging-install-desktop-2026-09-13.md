Última modificación: 2026-09-13

# Spec: Empaquetado Linux — Fase A (install usuario) + esbozo Fase B (.deb)

**Estado:** aprobado (chat 2026-09-13).  
**Intent:** `docs/intent/packaging-install-desktop-2026-09-13.md`  
**Rama:** `feat/packaging-fase-a-install-desktop`

## Objective

Instalar la app en el home del usuario con entrada de menú e icono; persistir config vía XDG cuando se lanza instalada. Dejar diseñada la Fase B (`.deb`) sin implementarla.

**Success Fase A:** `make install-user` → icono en menú GNOME → arranque correcto → config en `~/.config/…` → `make uninstall-user` limpia install.

---

## Fase A — Install de usuario

### Layout instalado

| Pieza | Ruta |
|-------|------|
| App root | `$XDG_DATA_HOME/whisper-live-captions/` (default `~/.local/share/whisper-live-captions/`) |
| Código | `$APP_ROOT/src/`, `requirements.txt`, `config.example.json` |
| Venv | `$APP_ROOT/.venv/` |
| Wrapper | `$XDG_BIN_HOME/whisper-live-captions` (default `~/.local/bin/whisper-live-captions`) |
| Desktop | `$XDG_DATA_HOME/applications/whisper-live-captions.desktop` |
| Icono | `$XDG_DATA_HOME/icons/hicolor/scalable/apps/whisper-live-captions.svg` |
| Config runtime | `$XDG_CONFIG_HOME/whisper-live-captions/config.json` |

`XDG_*` respeta variables de entorno; si no existen, los defaults POSIX de arriba.

### Comandos Make

| Target | Comportamiento |
|--------|----------------|
| `make install-user` | Copia árbol mínimo → crea/actualiza venv → `pip install -r requirements.txt` → escribe wrapper + `.desktop` + icono → `update-desktop-database` si existe |
| `make uninstall-user` | Borra `$APP_ROOT`, wrapper, `.desktop`, icono. **No** borra `$XDG_CONFIG_HOME/whisper-live-captions/` por defecto. `make uninstall-user PURGE_CONFIG=1` sí la borra. |

Idempotente: reinstalar sobrescribe código/wrapper/desktop/icono; reutiliza venv si existe (upgrade deps).

### Árbol mínimo a copiar

Incluir: `src/`, `requirements.txt`, `config.example.json`, `packaging/` (assets desktop/icono).  
Excluir: `.venv/`, `.git/`, `tests/`, `docs/`, `debug/`, `__pycache__/`, `config.json` del repo (no contaminar install con config de desarrollo).

### Wrapper (`whisper-live-captions`)

Bash ejecutable que:

1. Fija `APP_ROOT` al directorio instalado.
2. Activa `$APP_ROOT/.venv`.
3. Exporta `PYTHONPATH=$APP_ROOT`, `WLCL_APP_ROOT=$APP_ROOT`, `WLCL_CONFIG_DIR=$XDG_CONFIG_HOME/whisper-live-captions` (resuelto).
4. Prefija libs PyQt6 en `LD_LIBRARY_PATH` / `QT_PLUGIN_PATH` (mismo criterio que `scripts/run.sh`).
5. `QT_QPA_PLATFORM=xcb` por defecto.
6. `exec python -m src.app "$@"`.

### Desktop entry

```desktop
[Desktop Entry]
Type=Application
Version=1.0
Name=Whisper Live Captions
Comment=Subtítulos locales con Whisper (Linux)
Exec=whisper-live-captions
Icon=whisper-live-captions
Terminal=false
Categories=AudioVideo;Utility;
StartupNotify=true
```

`Exec` debe resolver el wrapper en `$PATH` (`~/.local/bin` suele estar en PATH en Ubuntu reciente; si no, el install imprime aviso).

### Icono

Emblema circular (sello “L”, sin wordmark) en canvas cuadrado con ~8% de margen, generado desde `assets/media/FullLogo_Transparent.png` vía `scripts/generate-app-icons.py`. Artefactos: `packaging/icons/whisper-live-captions.svg` (scalable) + PNG 32/48/64/128/256. El wordmark completo no se usa en el menú: en tile cuadrado queda ilegible y con demasiado aire.

### Resolución de config (runtime)

Nueva lógica en `src/config.py` / `src/app.py`:

| Modo | Condición | `config.json` |
|------|-----------|---------------|
| Instalado | `WLCL_CONFIG_DIR` definido **o** `WLCL_APP_ROOT` definido | `$WLCL_CONFIG_DIR/config.json` (crear dir si falta) |
| Desarrollo | ninguno de los anteriores | `Path.cwd() / "config.json"` (comportamiento actual) |

Primera ejecución instalada sin fichero: `validate_config({})` / defaults de `config.example.json` empaquetado; al guardar, escribe en XDG.

`config.example.json` se lee desde `WLCL_APP_ROOT` si está definido; si no, desde raíz del repo (como hoy).

**Migración opcional (Always):** si modo instalado y no existe config XDG pero existe `./config.json` en cwd, **no** auto-copiar (evita sorpresas). Documentar en README cómo copiar a mano.

### Arranque desarrollo sin regressión

- `make run` / `scripts/run.sh` **no** definen `WLCL_APP_ROOT` ni `WLCL_CONFIG_DIR` → config en cwd.
- Tests usan `tmp_path` / paths explícitos → sin cambio de contrato si `load_config(path)` recibe path.

### Prerequisites (documentar, no instalar)

NVIDIA drivers, Python 3.12, `pactl`/`parec` (`pulseaudio-utils`). El install-user falla con mensaje claro si no hay `python3.12`.

### Tests

| Tipo | Qué |
|------|-----|
| Unit | `resolve_config_path` / `resolve_app_root` respetan env y fallback cwd |
| Unit | Defaults / `load_config` sin fichero en dir XDG temporal |
| Manual | `make install-user` → aparece en menú → arranca → guarda Settings → reinicia y persiste; `make uninstall-user` quita icono |

### README

Sección **Instalación (usuario)** con `make install-user`, PATH, uninstall, y nota de que Fase B (.deb) está planificada.

---

## Always / Ask / Never

**Always**

- Prefijar libs PyQt6 en el wrapper (evitar Qt del sistema/Cursor).
- Config instalada solo bajo XDG config.
- Idempotencia de install-user.
- No borrar config de usuario en uninstall salvo `PURGE_CONFIG=1`.

**Ask**

- Cambiar el `Name=` del `.desktop` / id de aplicación.
- Incluir más assets de branding.

**Never (Fase A)**

- Requerir `sudo`.
- Flatpak / Snap / AppImage.
- Empaquetar modelos Whisper/NLLB.
- Escribir config en `$APP_ROOT`.

---

## Fase B — `.deb` (solo planificada; no implementar en esta rama)

### Objetivo

Artefacto `whisper-live-captions_<ver>_amd64.deb` instalable con `sudo dpkg -i`, entrada de menú system-wide.

### Layout propuesto

| Pieza | Ruta |
|-------|------|
| App | `/opt/whisper-live-captions/` |
| Wrapper | `/usr/bin/whisper-live-captions` |
| Desktop | `/usr/share/applications/whisper-live-captions.desktop` |
| Icono | `/usr/share/icons/hicolor/scalable/apps/whisper-live-captions.svg` |
| Config | sigue en XDG del usuario (no en `/etc` salvo defaults de solo lectura) |

### Dependencias Debian (propuesta)

`python3.12`, `python3.12-venv`, `pulseaudio-utils`; Recommends/Suggests: drivers NVIDIA (documentar; el paquete no puede depender de un `.deb` propietario concreto de forma portátil).

### Build

- Tooling: `nfpm` o `dpkg-deb` desde staging generado por script `packaging/build-deb.sh`.
- CI opcional: GitHub Release con el `.deb` al tagear `v*`.
- `postinst`: `update-desktop-database`, `gtk-update-icon-cache` si aplica.
- Misma lógica `WLCL_APP_ROOT` / `WLCL_CONFIG_DIR` que Fase A.

### Fuera de B v1

- PPA.
- Firma apt repository.
- Paquete que bundle CUDA.
- Auto-update.

### Criterio de salida B (futuro)

1. `dpkg -i` en Ubuntu 24.04 limpia → icono en menú → arranque.
2. Desinstalación `apt remove` limpia binaries/desktop; config usuario intacta.
3. Licencias/README del paquete mencionan NLLB NC.

---

## Acceptance Fase A

1. Rama `feat/packaging-fase-a-install-desktop` con packaging + XDG paths.
2. `make install-user` / `make uninstall-user` documentados y funcionales.
3. Icono visible en menú GNOME tras install (manual).
4. Config instalada en XDG; `make run` en repo sigue usando cwd.
5. Tests unitarios de resolución de paths verdes; `make test` / `make lint` verdes.
6. Spec Fase B esbozada arriba (sin código `.deb`).

## Siguiente

Plan/tasks → implementar Fase A slice a slice.
