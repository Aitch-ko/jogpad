# Notes for coding agents

Read [CONTRIBUTING.md](CONTRIBUTING.md) first; its rules apply to agents too.

## Layout

| Path | What |
| --- | --- |
| `src/jogpad/core.py` | key events to moves: steps, merging, locks, HOME, knob axis |
| `src/jogpad/moonraker.py`, `linux_input.py`, `service.py` | firmware, input devices, threads |
| `src/jogpad/config.py` | configuration schema (pydantic); source of `docs/reference/config.md` |
| `src/jogpad/cli.py` | command line; source of `docs/reference/cli.md` |
| `src/jogpad/api.py` | FastAPI app; source of `docs/reference/api.md` |
| `src/jogpad/i18n.py`, `src/jogpad/locales/` | message catalogs |
| `scripts/` | reference generator and the checks CI runs |
| `docs/` | Zensical documentation |

## Commands

```bash
pip install -e ".[dev,docs]"
ruff format . && ruff check . && mypy && pytest
python scripts/gen_reference.py          # after changing config, CLI or API
python scripts/check_i18n.py
zensical build --strict
```

## Rules

- English only in the repository.
- After changing configuration, CLI or API, regenerate `docs/reference/` and
  commit it. Never edit those pages by hand.
- New user-facing text: `t("literal.key")`, plus the key in `en.json` and
  `de.json`.
- Changed behaviour needs a change in `docs/` or the label `docs: not needed`.
- The HTTP API and the agent interface never move a machine.
- Commit trailer `Assisted-by: <agent>`, never `Co-Authored-By`.
