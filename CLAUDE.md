# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

A snake game built on [Pyxel](https://github.com/kitao/pyxel) (retro game engine, Pyxel 2.x API) with OmegaConf for YAML config. There is no dependency manifest, test suite or linter config.

## Commands

```bash
pip install pyxel omegaconf      # dependencies
python main.py                   # run the game; run from the repo root (assets.pyxres is loaded by relative path)
pyxel edit assets.pyxres         # edit sprites, tilemaps (level layouts), sounds and music
```

Set `debug: True` in `settings.yaml` to draw the snake's collision points and head center.

## Architecture

**Game loop and state machine (`main.py`, `states/`).** `Game` owns the global config (`settings.yaml`), score, level counter, `SoundManager` and one `GameStateHandler` per `StateID`. `pyxel.run(update, draw)` calls the current handler's `update`/`draw`. `change_state()` stops music, sets mouse visibility and starts the new state's music (`is_visible()`, `get_music()`), but only stores `next_stateID`. The switch happens at the end of `draw()`, so the old state finishes its frame first. Handlers are created once in `Game.start()`, except `RunningStateHandler`, which `restart()` and `level_up()` replace with a fresh instance (and with it a fresh `Map`, `Snake` and `Cam`). Overlay states (pause, death, countdown) do not `cls`, so they draw on top of the last running frame. On its first update a new `RunningStateHandler` switches to `COUNTDOWN`, which switches back to `RUNNING` after 3 seconds.

**Time.** Movement-independent timing uses wall-clock `datetime` deltas (`game.dt`, set each update), not frame counts: snake growth delay, `Timer`, enemy behavior and weapon cooldown all work this way.

**Screen layout and coordinates.** The window is `header + area + footer` tall (`settings.yaml`). World coordinates include the header height in y: entity/snake positions are offset by `cfg.header.h`, and tilemap lookups subtract it again (`(pos.y - header.h) // 8`). `Cam` computes a draw `offset` that keeps the snake head centered, clamped to the map borders. Every `draw(offset)` in the world adds it.

**Levels (`map.py`, `levels/<n>.yaml`).** `Map(level=game.level_counter)` loads `levels/{n}.yaml`:
- `tm`: index of the Pyxel tilemap in `assets.pyxres` holding the layout; `width`/`height` in pixels; `start` position.
- `goal`: win conditions, all of which must hold: `score` (counted from the level's start score) and/or `length` (segments).
- `timers`: named entries with `duration`, `frequency` (0 = fire once), `fire_n` (0 = unlimited) and a `callback` of `type: spawn` (`entity: apple|golden|enemy`, optional `pos`) or `type: grow` (`value`). They are turned into closures by `Map.create_callback`.

Tile semantics are hardcoded: tile `(0,0)` is empty and tile `(0,3)` is a wall (`check_on_wall`). Any other tile that matches an entity class's `_img_x/_img_y` (8px-tile coordinates in image bank 0) is spawned as that entity, and the tile is erased from the tilemap at load time. That changes the tilemap in memory, which is why `restart()` calls `pyxel.load` again. Level numbers are consecutive (`level_up` increments by 1). Only 1–3 and 9 exist, plus a scratch `_temp.yaml`.

**Entities (`entity.py`).** Subclass `Entity`, set `_img_x/_img_y` to the sprite tile and override `on_intersect` (snake head touches it), `update` and optionally `hit`. Then add the class to `ALL_ENTITIES` so the tilemap can place it, and to the name dict in `Map.create_callback` so timers can spawn it. Entities are removed by setting `alive = False`. `Map.update` drops dead entities, timers and projectiles at the start of the next update.

**Snake (`snake.py`).** The head moves along `orient` (degrees, Pyxel's `cos`/`sin`), and each segment takes the previous position of the one ahead of it. `grow > 0` appends segments one at a time with a delay, and `grow < 0` truncates. Collisions with walls and entities test two points from `get_collision_points()`, not the whole circle. `Projectile`/`Weapon`/`Gun` live here as well and are only partly wired up: `snake.weapon` is never set.

**UI (`widget.py`).** `Widget` sizes itself automatically from text lines and an optional `ImgInfo` sprite. `add_sub_widget` makes child coordinates relative to the parent. `Button` handles hover, click and an optional hotkey in `update()`. `LifeBar` is unfinished (it calls `super(LifeBar)` incorrectly).

Colors and other tuning values are module-level constants (e.g. `TURN_SPEED`, `MAX_SPEED`, `COL_*`) at the top of each file.
