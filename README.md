# GromacsGUI

A desktop graphical interface for [GROMACS](https://www.gromacs.org/), the molecular dynamics
simulation package. GROMACS is normally driven entirely from the command line through a series of
`gmx` subcommands and configuration files (`.mdp`), which can be a steep entry point for newcomers.
GromacsGUI wraps that workflow in a step-by-step wizard so a full simulation — from a structure file
to a production run — can be set up and launched without touching a terminal, while still showing and
letting you edit every file GROMACS actually uses.

## Status

Early development (Phase 1): system preparation, minimization, NVT/NPT equilibration, and production,
wrapped in a PySide6 desktop wizard. See `docs/` for the project roadmap.

## Requirements

- Python 3.11+
- A working GROMACS installation (`gmx` on `PATH`, or its `GMXRC` location configured in-app)
- PySide6 (installed automatically as a dependency)

## Development setup

```bash
conda create -n gromacsgui -c conda-forge python=3.11 git -y
conda activate gromacsgui
pip install -e ".[dev]"
```

Run the app:

```bash
python -m gromacs_gui.app
```

Run the tests (unit tests only; integration tests that need a real `gmx` binary are marked
`requires_gmx`):

```bash
pytest -m "not requires_gmx"
```

## License

GPLv3 — see [LICENSE](LICENSE). Chosen so that anyone who builds on GromacsGUI (including
forks that add features) must keep their version open and share their source, rather than
turning it into a closed competing product.
