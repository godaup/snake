# Snake Quest

A level-based snake game built with [Pyxel](https://github.com/kitao/pyxel).

## Install and play

```bash
pip install snake-quest   # or, from a checkout: pip install .
snake-quest               # or: python -m snake_quest
```

Options: `--level N` to start (and restart) at a level, `--scale N` for the window size, `--mute`, `--debug`, `--version`.
On Linux, Pyxel needs the system SDL2 library (e.g. `apt install libsdl2-2.0-0`).

Controls: arrow keys (or gamepad D-pad) to steer, `P` to play/pause, `R` to restart and `Q` to quit after a game over.

## Development

```bash
pip install -e . --group dev   # needs pip >= 25.1
pytest
ruff check . && ruff format --check .
pyxel edit src/snake_quest/resources/garden.pyxres
```

## Roadmap

20 levels in 4 story arcs, each level with its own twist: see [ROADMAP.md](ROADMAP.md).
