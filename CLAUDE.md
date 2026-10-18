# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

**Snake Quest**: a level-based snake game built on [Pyxel](https://github.com/kitao/pyxel) (retro game engine, Pyxel 2.x API) with OmegaConf for YAML config. It's distributed as `snake-quest` (the name `snake` is taken on PyPI). The code lives in `src/snake_quest/`, and everything is configured in `pyproject.toml`: hatchling build, dependencies, the `dev` dependency group, the `snake-quest` console script, ruff and pytest. Game data (`settings.yaml`, `levels/`, `resources/*.pyxres`) is package data next to the code and is located via `Path(__file__).parent`. Module imports are absolute (`from snake_quest.map import Map`). `ROADMAP.md` holds the plan (20 levels in 4 arcs, milestones M0–M5): tick its checkboxes when a milestone item is done.

Pyxel is pinned to exactly `2.9.9` (uploaded 2026-08-12). In October 2026 the upstream author's GitHub account (`kitao`) was suspended after his token was abused in the "GhostAction" attacks, and the pin keeps out any release published during that time. Don't widen it until the account is back and new releases can be checked against the upstream repo. Until then, github.com/kitao/pyxel returns 404, and the docs are mirrored at kitao.dev/pyxel.

## Commands

```bash
pip install -e . --group dev          # editable install + pytest + ruff (pip >= 25.1; Linux also needs system SDL2)
snake-quest                           # run the game (or python -m snake_quest); --level N --scale N --mute --debug
pyxel edit src/snake_quest/resources/garden.pyxres   # edit sprites, sounds and arc 1 tilemaps (level layouts)
snake-quest --level maze --preview maze.png   # render a whole level (walls, entities, path, start) to a PNG
python tools/draft_maze.py src/snake_quest/resources/garden.pyxres --level src/snake_quest/levels/maze.yaml \
    --src-tm 2 --dst-tm 3 --seed 7    # regenerate the maze draft around the path tiles (see the script's docstring)
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

**Campaign (`campaign.py`, `levels/campaign.yaml`).** The campaign lists arcs in order. Each arc has a name, a `resources` `.pyxres` file in `resources/` and its levels by file name. `game.level_counter` is the 1-based number in the whole campaign. `campaign.level(n)` returns a `Level` (name, arc, path, resource file). `--level` accepts a number or a name. Images, sounds and music come only from the top-level `sprites` file, loaded once in `Game.start()`. Every `Map` calls `level.load_tilemaps()`, which loads only the tilemaps of its arc's file, so each level starts from fresh tilemaps. `pyxel.load` replaces the `Tilemap` objects, so never keep a reference to `pyxel.tilemaps[i]` across a load. `pyxel.init()` changes the process's working directory to the directory of the module that calls it, so resolve user-given paths before calling it (as `--preview` does). Winning the last level shows `VictoryStateHandler`. A level file that is not in the campaign fails the tests, unless its name starts with `_` (scratch levels, excluded from builds).

**Levels (`map.py`, `levels/<name>.yaml`).** `Map(level=campaign.level(n))` loads the level file:
- `tm`: index (0–7) of the Pyxel tilemap in the arc's resource file holding the layout; `width`/`height` in pixels; `start` position.
- `goal`: win conditions, all of which must hold. The types live in the `GOALS` registry in `goals.py`: `score: N` (counted from the level's start score), `length: N`, `exit: [x, y]` (head on a tile showing that sprite tile), `survive: seconds`, `defeat: N` (entities killed by `hit()`, counted in `map.defeated`; eating doesn't count), `hold_length: {length, seconds}` (in a row) and `collect_all: <entity name>`. A new type is a `Goal` subclass with `key`, `done()`, `describe()` and optionally `update()` for time-based goals, added to `GOALS`. Unknown or missing goals raise when the map loads.
- `timers`: named entries with `duration`, `frequency` (0 = fire once), `fire_n` (0 = unlimited) and a `callback` of `type: spawn` (`entity: apple|golden|enemy`, optional `pos`) or `type: grow` (`value`). They are turned into closures by `Map.create_callback`.

Tile semantics are hard-coded as `EMPTY_TILE = (0, 0)` and `WALL_TILE = (0, 3)` in `map.py`, and `map.tile_at(pos)` returns the sprite tile at a world position. Walls are painted with `WALL_TILE` in the editor. When a map loads, `_autotile_walls()` replaces each one with the hedge variant `(mask, 8)` that matches its wall neighbours (mask bits N=1, E=2, S=4, W=8; outside the map counts as wall). So collision checks must use `WALL_TILES`, never `WALL_TILE`. `DECOR_TILES` (row 9: grass, flowers, a stone) are drawn but walkable and free for spawning; `FLOOR_TILES` is empty plus decorations. `PATH_TILE = (3, 0)` is a level design helper marking the intended route (the maze's pathway). The maze plays from tilemap 3, a draft generated by `tools/draft_maze.py` from the hand-made layout and path in tilemap 2 (kept for reference): an 8-tile cell grid whose only route to the golden apples follows the path cells. Like entity tiles, path tiles are lifted out of the tilemap when the map loads and kept in `map.path`. They are drawn as breadcrumbs only after `map.reveal_path()` or with `debug` on. After loading, a tilemap may contain only floor and wall tiles, and a test fails on any stray tile. Any other tile that matches an entity class's `_img_x/_img_y` (8px-tile coordinates in image bank 0) is spawned as that entity, and the tile is erased from the tilemap at load time. That changes the tilemap in memory, which is why every `Map` reloads its tilemaps.

**Entities (`entity.py`).** Subclass `Entity`, set `_img_x/_img_y` to the sprite tile and override `on_intersect` (snake head touches it), `update` and optionally `hit`. Then add the class to `ALL_ENTITIES` so the tilemap can place it, and to `ENTITY_NAMES` so level files (timers, goals) can refer to it. Entities are removed by setting `alive = False`. `Map.update` drops dead entities, timers and projectiles at the start of the next update.

**Snake (`snake.py`).** The head moves along `orient` (degrees, Pyxel's `cos`/`sin`), and each segment takes the previous position of the one ahead of it. `grow > 0` appends segments one at a time with a delay. `grow < 0` cuts `|grow|` segments every frame for as long as it stays negative (intended), and raises `RuntimeError("Dead")` once the snake is shorter than that. Collisions with walls and entities test two points from `get_collision_points()`, not the whole circle. `Projectile`/`Weapon`/`Gun` live here as well and are only partly wired up: `snake.weapon` is never set.

**UI (`widget.py`).** `Widget` sizes itself automatically from text lines and an optional `ImgInfo` sprite. `add_sub_widget` makes child coordinates relative to the parent. `Button` handles hover, click and an optional hotkey in `update()`. `LifeBar` fills `val` (0–1) of its width with `fg` over `bg`.

Colors and other tuning values are module-level constants (e.g. `TURN_SPEED`, `MAX_SPEED`, `COL_*`) at the top of each file.
