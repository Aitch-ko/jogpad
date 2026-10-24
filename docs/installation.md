# Installation

!!! note
    jogpad has not been released yet. These steps describe the development
    setup.

jogpad needs Python 3.10 or newer. Raspberry Pi OS 11 (Bullseye) ships Python
3.9 and is not supported; Raspberry Pi OS 12 (Bookworm) ships 3.11.

```bash
git clone https://github.com/Aitch-ko/jogpad.git
cd jogpad
python3 -m venv .venv
.venv/bin/pip install -e ".[dev]"
.venv/bin/jogpad --version
```

Run the API without a pad attached:

```bash
.venv/bin/jogpad serve
```

Then open `http://127.0.0.1:7150/docs` for the Swagger UI.
