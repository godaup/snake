# Roadmap

Snake is the starting point, not the limit: **every level gives the game its own twist.** The campaign has
**20 levels in 4 story arcs**, and each arc ends with a boss level (5, 10, 15, 20). Difficulty and mechanics ramp up
gradually. A level introduces at most one new mechanic, and later levels combine them.

Ground rules:

- **A level = a YAML file + at most one new mechanic in code.** Engine features (goal types, tiles, entities, weapons)
  are data-driven, so most new levels are level design, not programming.
- **One `.pyxres` per arc.** Each arc brings its own tilemaps (Pyxel only has 8 tilemaps of 256×256 tiles per resource
  file); shared sprites and sounds live in one place.
- **Every level must be winnable**, and a test plays it through to prove it (see M5).
- **Levels are tuned for Medium.** Easy, Hard and Nightmare scale them (`difficulty.py`); a level overrides values
  only where scaling isn't enough. The bot's win rate per difficulty must stay in its band (`pytest -m slow`).

## Campaign

### Arc 1: The Garden (movement and space)

| #  | Level              | Twist                                                                                  | Goal                    | Status                        |
|----|--------------------|----------------------------------------------------------------------------------------|-------------------------|-------------------------------|
| 1  | Classic            | Plain snake, learn to steer: one apple at a time                                       | score                   | exists (score 20)             |
| 2  | Yummy              | Feast in the same small room: golden apples rain, the snake grows fast                 | score                   | score 250: needs playtesting  |
| 3  | Maneuver           | Large scrolling map with portals / wrap-around                                         | score                   | exists                        |
| 4  | The Maze           | Navigation: follow the (hidden) pathway to the golden apples at its end               | eat all golden apples   | exists; layout incomplete     |
| 5  | **Boss: The Hunger** | Starving in the dark: constant shrinking, scarce food, a light radius around the head; the hunger bar is the boss bar | survive until dawn | exists (needs playtesting) |

### Arc 2: The Wilds (hunters and prey)

| #  | Level              | Twist                                                         | Goal                 |
|----|--------------------|---------------------------------------------------------------|----------------------|
| 6  | Hunted             | Beetles wake up and chase the snake, biting off its tail      | survive N seconds (exists) |
| 7  | Armed              | First weapon: **Gun**                                         | defeat N enemies (exists) |
| 8  | Prey               | Golden critters flee from the snake (new "flee" behavior)    | collect all (exists) |
| 9  | Burrows            | Nests keep spawning enemies until destroyed                   | destroy all nests (exists) |
| 10 | **Boss: The Alpha** | Pack leader that chases and calls in hunters from its burrows | defeat the boss (exists) |

### Arc 3: The Fortress (firepower and defense)

| #  | Level             | Twist                                                         | Goal               |
|----|-------------------|---------------------------------------------------------------|--------------------|
| 11 | Turrets           | Turrets shoot back; a hit cuts the snake at that segment      | length / score     |
| 12 | Swarm             | Many small enemies; **Spread** shot                           | defeat N enemies   |
| 13 | Ice               | Turning drifts; **Ricochet** shots bounce off walls           | reach the exit     |
| 14 | Minefield         | **Mines** dropped from the tail; enemies follow the trail     | defeat N enemies   |
| 15 | **Boss: The Core** | Shielded core with turret phases                              | defeat the boss    |

### Arc 4: Ouroboros (everything at once)

| #  | Level                | Twist                                                         | Goal                 |
|----|----------------------|---------------------------------------------------------------|----------------------|
| 16 | Trail                | The snake's path turns into walls                             | survive / score      |
| 17 | Mirror               | Inverted controls                                             | reach the exit       |
| 18 | Armored              | Armored enemies that only the **Laser** pierces               | defeat N enemies     |
| 19 | Gauntlet             | Timed run through earlier twists; **Homing** shots            | reach the exit       |
| 20 | **Boss: Ouroboros**  | A rival AI snake that eats, grows and shoots like the player  | defeat the boss      |

### Weapons

| Weapon   | Introduced | Projectile behavior                         |
|----------|------------|---------------------------------------------|
| Gun      | 7          | single straight shot (exists)               |
| Spread   | 12         | fan of three shots                          |
| Ricochet | 13         | bounces off walls                           |
| Mines    | 14         | dropped behind the tail, area damage        |
| Laser    | 18         | piercing beam                               |
| Homing   | 19         | steers towards the nearest enemy            |

`Weapon.next_pattern()` already returns a list of projectiles. The rest needs projectile behaviors (pierce, bounce,
home, explode, lifetime), weapon pickups and switching, and ammo/cooldown in the footer HUD.

## Milestones

### M0: Foundations

- [x] Campaign file: levels are referenced by name and ordered per arc in `levels/campaign.yaml` (fixes the crash
      after the last level)
- [x] One `.pyxres` per arc: shared sprites and sounds from one file, tilemaps from the arc's file, reloaded for each
      level
- [x] Goal types beyond `score` / `length`: `exit`, `survive`, `defeat`, `hold_length`, `collect_all`
- [x] Entity and tile registries by name (replace the hard-coded lists in `entity.py` / `map.py`), new tile types
      (exit, portal, hazard)
- [x] Level intro (mission briefing), countdown and level-complete screen
- [x] Header and footer HUD: level and title, score, best score, length; per-goal status and progress bars (timer, counters)
- [ ] HUD for mechanics still to come: health (ammo and the boss bar exist)
- [x] Sound effects on events (eat, hit, death, win)
- [x] Input layer: steering through a controller interface instead of `pyxel.btn`, so tests, bots and the rival snake
      can play
- [x] Debug overlay (mouse → tile coordinates) and removal of leftovers (dead code, unused settings, debug prints)

### M1: Arc 1

Done: complete maze layout around the pathway (tilemap 3), natural Maneuver layout (tilemap 4), floor decorations, the firefly that lights the maze's breadcrumbs, speed apples, portal pairs in Maneuver, darkness with a light radius (level option `darkness`), boss framework (`bosses.py`: boss bar, phases, banner) and The
Hunger. Classic, Yummy and The Hunger rebalanced after playtests (Yummy moved to stage 2, golden apples every 3 s, 250 points);
Classic and The Hunger are checked with a bot (`tests/test_winnable.py`), Yummy's goal is beyond the bot. Open: more playtesting, winnability tests for Maneuver and The Maze.

### M2: Arc 2

Done: `arc2.pyxres` and the arc in the campaign, Hunted (level 6) with the `Hunter` (sleeps, wakes, chases the
tail along the shortest way, bites off chunks), bot avoidance of hostile entities; Armed (level 7) with the Gun
(`weapons.py`), gun pickups that add ammo, ammo in the HUD and a bot that aims and shoots. Prey (level 8) with
fleeing critters, Burrows (level 9) with nests, Boss: The Alpha (level 10). Open: playtesting.

### M3: Arc 3

Turrets, weapon system (Spread, Ricochet, Mines), ice steering, The Core.

### M4: Arc 4

Trail walls, mirrored input, Laser and Homing, AI-controlled rival snake (reusing `Snake` through the input layer).

### M5: Release

- [x] Menu theme song, animated main menu, highscores, snake colour palettes, credits (saved per user)
- [x] Difficulty setting (Easy, Medium, Hard, Nightmare) chosen in the menu, one highscore table per difficulty,
      bot-checked win-rate bands (`tools/balance.py`, `tests/test_winnable.py`)
- [x] Checkpoints and level select: a finished arc can be started directly (`states/select.py`)
- [ ] Level music, initials for highscores
- [ ] A winnability test per level (`PathController` bot in `tests/test_winnable.py`: Classic, The Hunger; input layer, later `pyxel-mcp` once the upstream GitHub account is restored)
- [ ] `snake-quest` 0.x on PyPI
