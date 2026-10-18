# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

**Snake Quest**: a level-based snake game built on [Pyxel](https://github.com/kitao/pyxel) (retro game engine, Pyxel 2.x API) with OmegaConf for YAML config. It's distributed as `snake-quest` (the name `snake` is taken on PyPI). The code lives in `src/snake_quest/`, and everything is configured in `pyproject.toml`: hatchling build, dependencies, the `dev` dependency group, the `snake-quest` console script, ruff and pytest. Game data (`settings.yaml`, `levels/`, `assets.pyxres`) is package data next to the code and is located via `Path(__file__).parent`. Module imports are absolute (`from snake_quest.map import Map`).

Pyxel is pinned to exactly `2.9.9` (uploaded 2026-08-12). In October 2026 the upstream author's GitHub account (`kitao`) was suspended after his token was abused in the "GhostAction" attacks, and the pin keeps out any release published during that time. Don't widen it until the account is back and new releases can be checked against the upstream repo. Until then, github.com/kitao/pyxel returns 404, and the docs are mirrored at kitao.dev/pyxel.

## Commands

```bash
pip install -e . --group dev          # editable install + pytest + ruff (pip >= 25.1; Linux also needs system SDL2)
snake-quest                           # run the game (or python -m snake_quest); --level N --scale N --mute --debug
pyxel edit src/snake_quest/assets.pyxres   # edit sprites, tilemaps (level layouts), sounds and music
pytest                                # run all tests
pytest tests/test_map.py::test_new_pos_is_free   # run a single test
ruff check . && ruff format --check .            # lint + format check
```

CI (`.github/workflows/ci.yml`) runs lint, format check and pytest. It then builds the wheel and runs `snake-quest --version` from a fresh venv, which catches package data or entry points missing from the build. `levels/_temp.yaml` is a scratch level and is excluded from builds.

## Tests

Tests run against the installed package, so do the editable install first. Tests that need Pyxel (`Map`, state handlers, widgets) rely on the session fixture in `tests/conftest.py`, which calls `pyxel.init(..., headless=True)` once. Request the `assets` fixture to get freshly loaded tilemaps (Map mutates them). `Game` cannot be built in tests because it enters `pyxel.run`; use the `game` fixture (`FakeGame`) instead, which records `change_state` calls in `requested_states`. Known bugs are kept as `xfail(strict=True)` tests, so fixing one makes that test fail until the marker is removed.

## Architecture

**Entry point (`cli.py`).** `main()` parses arguments, turns them into a dict of overrides that `Game(overrides=..., start_level=...)` merges over `settings.yaml` in `reload_settings()`, and only then imports `game`, so `--help` and `--version` don't touch Pyxel. New command-line options should become settings overrides the same way.

**Game loop and state machine (`game.py`, `states/`).** `Game` owns the global config (`settings.yaml`), score, level counter, `SoundManager` and one `GameStateHandler` per `StateID`. `pyxel.run(update, draw)` calls the current handler's `update`/`draw`. `change_state()` stops music, sets mouse visibility and starts the new state's music (`is_visible()`, `get_music()`), but only stores `next_stateID`. The switch happens at the end of `draw()`, so the old state finishes its frame first. Handlers are created once in `Game.start()`, except `RunningStateHandler`, which `restart()` and `level_up()` replace with a fresh instance (and with it a fresh `Map`, `Snake` and `Cam`). Overlay states (pause, death, countdown) do not `cls`, so they draw on top of the last running frame. On its first update a new `RunningStateHandler` switches to `COUNTDOWN`, which switches back to `RUNNING` after 3 seconds.

**Time.** Movement-independent timing uses wall-clock `datetime` deltas (`game.dt`, set each update), not frame counts: snake growth delay, `Timer`, enemy behavior and weapon cooldown all work this way.

**Screen layout and coordinates.** The window is `header + area + footer` tall (`settings.yaml`). World coordinates include the header height in y: entity/snake positions are offset by `cfg.header.h`, and tilemap lookups subtract it again (`(pos.y - header.h) // 8`). `Cam` computes a draw `offset` that keeps the snake head centered, clamped to the map borders. Every `draw(offset)` in the world adds it.

**Levels (`map.py`, `levels/<n>.yaml`).** `Map(level=game.level_counter)` loads `levels/{n}.yaml`:
- `tm`: index of the Pyxel tilemap in `assets.pyxres` holding the layout; `width`/`height` in pixels; `start` position.
- `goal`: win conditions, all of which must hold: `score` (counted from the level's start score) and/or `length` (segments).
- `timers`: named entries with `duration`, `frequency` (0 = fire once), `fire_n` (0 = unlimited) and a `callback` of `type: spawn` (`entity: apple|golden|enemy`, optional `pos`) or `type: grow` (`value`). They are turned into closures by `Map.create_callback`.

Tile semantics are hardcoded: tile `(0,0)` is empty and tile `(0,3)` is a wall (`check_on_wall`). Any other tile that matches an entity class's `_img_x/_img_y` (8px-tile coordinates in image bank 0) is spawned as that entity, and the tile is erased from the tilemap at load time. That changes the tilemap in memory, which is why `restart()` calls `pyxel.load` again. Level numbers must be consecutive (`level_up` increments by 1). Only 1–3 and 9 exist, plus a scratch `_temp.yaml`, so winning level 3 crashes (see `tests/test_levels.py`).

**Entities (`entity.py`).** Subclass `Entity`, set `_img_x/_img_y` to the sprite tile and override `on_intersect` (snake head touches it), `update` and optionally `hit`. Then add the class to `ALL_ENTITIES` so the tilemap can place it, and to the name dict in `Map.create_callback` so timers can spawn it. Entities are removed by setting `alive = False`. `Map.update` drops dead entities, timers and projectiles at the start of the next update.

**Snake (`snake.py`).** The head moves along `orient` (degrees, Pyxel's `cos`/`sin`), and each segment takes the previous position of the one ahead of it. `grow > 0` appends segments one at a time with a delay. `grow < 0` cuts `|grow|` segments every frame for as long as it stays negative (intended), and raises `RuntimeError("Dead")` once the snake is shorter than that. Collisions with walls and entities test two points from `get_collision_points()`, not the whole circle. `Projectile`/`Weapon`/`Gun` live here as well and are only partly wired up: `snake.weapon` is never set.

**UI (`widget.py`).** `Widget` sizes itself automatically from text lines and an optional `ImgInfo` sprite. `add_sub_widget` makes child coordinates relative to the parent. `Button` handles hover, click and an optional hotkey in `update()`. `LifeBar` fills `val` (0–1) of its width with `fg` over `bg`.

Colors and other tuning values are module-level constants (e.g. `TURN_SPEED`, `MAX_SPEED`, `COL_*`) at the top of each file.
