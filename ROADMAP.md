# Roadmap

Snake is the starting point, not the limit: **every level gives the game its own twist.** The campaign has
**35 levels in 7 story arcs**, and each arc ends with a boss level (5, 10, 15, ..., 35). Difficulty and mechanics ramp
up gradually. A level introduces at most one new mechanic, and later levels combine them. The seven arcs are below in
order of play: the Caves, the Workshop and Space were built from the [Expansion](#expansion) after the first four,
and placed before Ouroboros, the finale. So was a bonus arc after the story, The Keeper, where the snake moves on its
own. The Expansion still plans one-off levels.

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
| 11 | Turrets           | Turrets shoot back; a hit cuts the snake at that segment      | length (exists)    |
| 12 | Swarm             | Many small enemies; **Spread** shot                           | defeat N (exists)  |
| 13 | Ice               | Turning drifts; **Ricochet** shots bounce off walls           | turrets, exit (exists) |
| 14 | Minefield         | **Mines** dropped from the tail; enemies follow the trail     | defeat N (exists)  |
| 15 | **Boss: The Core** | Shielded core with turret phases                              | defeat the boss (exists) |

### Arc 4: The Caves (darkness and digging)

Builds on `darkness` and the hunters. New: a map that changes while playing (walls dug away or caving in).
Designed in detail in [docs/arc4-caves.md](docs/arc4-caves.md); built (see M6).

| #  | Level                 | Twist                                                              | Goal              |
|----|-----------------------|--------------------------------------------------------------------|-------------------|
| 16 | Webs                  | Spiders spin webs that hold the snake for a moment                 | collect all crystals, in time (exists) |
| 17 | Moles                 | Moles dig new tunnels through the walls, opening shortcuts for enemies | defeat N (exists) |
| 18 | Collapse              | A cave-in front chases the snake through a long tunnel              | reach the exit (exists) |
| 19 | Bats                  | Bats wake up in any light; **Flare** shots light the way and scare them | survive N seconds (exists) |
| 20 | **Boss: The Brood Mother** | A giant spider: egg sacs, then drops from the dark ceiling, webs the cave shut | defeat the boss (exists) |

### Arc 5: The Workshop (puzzles)

Sokoban for snakes: the level is a puzzle with one solution or a few, and timing matters less than the order of moves.
New: pushable objects and switches.
Designed in detail in [docs/arc5-workshop.md](docs/arc5-workshop.md) (a blocked crate stops the snake instead of
crashing it; bots follow a written solution, the level's `plan`); built (see M8).

| #  | Level                  | Twist                                                             | Goal              |
|----|------------------------|-------------------------------------------------------------------|-------------------|
| 21 | Crates                 | The head pushes crates onto plates to open gates; a lever resets the room | reach the exit (exists) |
| 22 | Pressure Plates        | Plates stay down only while the body lies on them: grow long enough to hold several | reach the exit (exists) |
| 23 | Keys                   | Keys carried in the body (as segments) open matching locks; mice bite them off | reach the exit (exists) |
| 24 | Conveyors              | Belts carry crates and the snake; levers reverse them             | reach the exit (exists) |
| 25 | **Boss: The Clockwork** | A machine opened only by jamming its gears, holding its springs and unlocking it | defeat the boss (exists) |

### Arc 6: Space (oxygen and inertia)

Builds on The Hunger's meter (oxygen drains, tanks refill it, the light shrinks as it runs low) and the ice drift
(little grip everywhere: the snake keeps its momentum).
Designed in detail in [docs/arc6-space.md](docs/arc6-space.md) (new weapon: the **Tractor**, which pulls pickups in); built
(see M7).

| #  | Level                  | Twist                                                             | Goal              |
|----|------------------------|-------------------------------------------------------------------|-------------------|
| 26 | Airlock                | Oxygen drains; air tanks refill it; airlock doors take turns      | score (exists)    |
| 27 | Zero-G                 | Inertia everywhere: turning only slowly bends the course; **Tractor** | grow, then the exit (exists) |
| 28 | Gravity Wells          | Planets pull on the snake's heading; slingshot around them        | collect all stars, in time (exists) |
| 29 | Asteroids              | Asteroids split when shot and bounce off the hull (wrap-around edges: later) | destroy all (exists) |
| 30 | **Boss: The Mothership** | A ship that circles through the gravity wells and drops raiders  | defeat the boss (exists) |

### Arc 7: Ouroboros (everything at once)

The end of the first 20 levels (arc 4 then), and the finale again once the Caves, the Workshop and Space
were built.

| #  | Level                | Twist                                                         | Goal                 |
|----|----------------------|---------------------------------------------------------------|----------------------|
| 31 | Trail                | The snake's path turns into walls                             | score (exists)       |
| 32 | Mirror               | Mirrored floor swaps left and right                           | length, exit (exists) |
| 33 | Armored              | Armored enemies that only the **Laser** pierces               | defeat N (exists)    |
| 34 | Gauntlet             | Timed run through every arc's twists: ice, mirrors, thorns, webs, belts, a planet; **Homing** shots | goldens, exit, in time (exists) |
| 35 | **Boss: Ouroboros**  | A rival AI snake that eats, grows and shoots like the player  | defeat the boss (exists) |

### Weapons

| Weapon   | Introduced | Projectile behavior                         |
|----------|------------|---------------------------------------------|
| Gun      | 7          | single straight shot (exists)               |
| Spread   | 12         | fan of three shots (exists)                 |
| Ricochet | 13         | bounces off walls (exists)                  |
| Mines    | 14         | dropped behind the tail, area damage (exists) |
| Flare    | 19         | burns on where it lands: a light that scares bats (exists) |
| Tractor  | 27         | no shot: pulls the nearest pickup ahead in (exists) |
| Laser    | 33         | piercing beam (exists)                      |
| Homing   | 34         | steers towards the nearest enemy (exists)   |

`Weapon.next_pattern()` already returns a list of projectiles. The rest needs projectile behaviors (pierce, bounce,
home, explode, lifetime), weapon pickups and switching, and ammo/cooldown in the footer HUD.

## Expansion

Ideas for after the first 20 levels. The Caves, the Workshop and Space came from here and are arcs 4-6 now (above),
played before Ouroboros, which became the finale again; Gauntlet got a stretch from each. Still here: the bonus arc
and the one-off levels.

### Bonus arc: The Keeper (the snake moves on its own)

Unlocked after the campaign. The bot (`PathController`) steers the snake, and the player shapes the world with the
mouse: build and remove walls, plant apple trees, set decoys that lure enemies away. Needs a mouse input layer and a
bot whose choices the player can read and predict. Goals as usual (score, length, survive), but reached for the snake.
Designed in detail in [docs/arc8-keeper.md](docs/arc8-keeper.md) (a pet bot that eats the nearest apple by walking
distance, keeps its choice and draws its way; a hand with budgets of hedges, trees, lures and lanterns; a second bot
plays the hand in tests, and the levels must be lost without it); built (see M9).

| #  | Level              | Twist                                                                  | Goal                      |
|----|--------------------|------------------------------------------------------------------------|---------------------------|
| 36 | Hedges             | Plant and lift hedges to lead the snake round thorns it can't see      | length (exists)           |
| 37 | Orchard            | Apple trees are the only food: where they stand steers the snake       | score, in time (exists)   |
| 38 | Lures              | Beetles hunt lures before the tail; hedge pens stop them               | hold a length (exists)    |
| 39 | Lanterns           | In the dark the snake sees only what is lit and walks to the lanterns  | all golden apples (exists) |
| 40 | **Boss: The Crow** | Lands to steal, swoops at the tail, calls its flock; bitten only while down | defeat the boss (exists) |

### One-off levels

Crazy levels to fit into an arc (or into the bonus arc) where they fit:

- **Shepherd:** critters flee from the snake (`map.flight`); the body is the fence that herds them into a pen. Goal:
  pen N animals.
- **Hydra:** a piece of tail that gets cut off comes alive as a hostile snake, so every hit makes a new enemy. Also a
  boss idea: a hydra that splits when shot.
- **Microscopic:** the snake is a virus inside a body: eating cells grows it, antibodies hunt it, and a fever (a timer)
  speeds everything up.
- **Paint:** the snake leaves colour on the floor, enemies paint over it. Goal: cover a share of the floor.

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

Done: `arc3.pyxres` with fortress layouts (`draft_garden.py fortress`, `tint` for stone walls), Turrets (level 11:
turrets that lead their shots, a hit cuts the snake where it strikes), Swarm (level 12: drones over the walls, the
Spread), Ice (level 13: drifting on ice, the Ricochet, turrets then the exit), Minefield (level 14: crawlers on the
trail, Mines), Boss: The Core (level 15: a shield held up by rings of turrets, drones). Weapon pickups switch weapons
(`WeaponPickup`); the bot dodges shots, drops mines and stocks ammo. Open: playtesting.

### M4: Arc 7 (Ouroboros)

Trail walls, mirrored input, Laser and Homing, AI-controlled rival snake (reusing `Snake` through the input layer).

Done: `arc7.pyxres` with temple layouts (`draft_garden.py temple`), Trail (level 31: the tail leaves walls that
crumble, crawlers on the trail), Mirror (level 32: bands of mirrored floor across the halls swap left and right), Armored (level 33: knights in
armour, the Laser), Gauntlet (level 34: ice, mirrors and thorns against the clock, `time_limit`, Homing), Boss: Ouroboros (level
35: a rival snake driven by the bot, with lives, that eats, grows, takes the guns and shoots). The campaign is complete.
Open: playtesting.

- [x] Moved to the end of the story (it was arc 4) once the Caves, the Workshop and Space were built, as the finale:
  Gauntlet got a stretch from each of them (webs, conveyor belts, a planet) and is 1920 px long now; the Clockwork
  drops Spread instead of Homing, which Gauntlet introduces.

### M6: Arc 4 (The Caves)

Done: `arc4.pyxres` with cave layouts (`draft_garden.py cave`, `scatter`, `webs`), the Caves music, Webs (level 16:
spiders spin webs that hold the snake, crystals against the clock), Moles (level 17: moles dig tunnels for good,
`map.dig`, and come up to be shot), Collapse (level 18: the `collapse` goal, a cave-in front through a long tunnel),
Bats (level 19: bats that wake in any light, the Flare), Boss: The Brood Mother (level 20: egg sacs, then drops from the
dark with a warning shadow). Open: playtesting.

### M7: Arc 6 (Space)

Done: `arc6.pyxres` with station and open-space layouts (`draft_garden.py station`, `void`), the Space music, Airlock
(level 26: the `oxygen` goal, air tanks, airlock doors that take turns), Zero-G (level 27: low `grip` everywhere, the
Tractor), Gravity Wells (level 28: planets that pull the heading, `map.pull`), Asteroids (level 29: rocks that split and
bounce), Boss: The Mothership (level 30: engine pods holding up a shield, a bay that opens and drops raiders, a tractor
beam). Open: the wrap-around edges for Asteroids (see docs/arc6-space.md), playtesting.

### M8: Arc 5 (The Workshop)

Done: `arc5.pyxres` with layouts written from puzzle texts (`tools/draft_workshop.py`, `tools/puzzles/`), plans
for bots checked by `tools/solve_workshop.py`, the Workshop music, Crates (level 21: crates the head pushes, a
stall at one that can't move, plates and gates, reset levers), Pressure Plates (level 22: the body holds plates),
Keys (level 23: keys as segments, locks, clockwork mice), Conveyors (level 24: belts and levers), Boss: The
Clockwork (level 25: jam its gears, hold its springs, bring keys to its locks; its hands cut). Open: boulders
(see docs/arc5-workshop.md), playtesting (puzzles need people more than any other arc).

### M9: The Keeper (bonus arc)

Done: `keeper.pyxres` with layouts written from garden texts (`tools/draft_keeper.py`, `tools/gardens/`), a bonus
arc after the story (`bonus: true`: the victory screen after level 35 as before, the arc open on the map once the
story is done, its own victory after level 40), the Keeper's waltz and three effects (plant, lift, caw), the pet
(`PetController`: nearest food by walking distance, a kept choice, blind to thorns, its way drawn), the hand (mouse,
keys or gamepad; budgets; sprouting hedges), Hedges (level 36), Orchard (level 37: apple trees), Lures (level 38:
lures, hedge pens), Lanterns (level 39: lanterns in the dark), Boss: The Crow (level 40: it steals, swoops and calls
its flock; a hedge across a swoop brings it down). A `HandBot` plays the hand in tests, and a slow test checks that
the pet left alone loses every level. Open: balancing (Hedges, Lures, Lanterns and the Crow are outside some win-rate bands: see "As built" in
docs/arc8-keeper.md), playtesting (above all: is the pet's way readable enough to plan with?),
the "keeper's breath" slow-down (see docs/arc8-keeper.md), the Shepherd as a Keeper level.

### M5: Release

- [x] Menu theme song, animated main menu, highscores, snake colour palettes, credits (saved per user)
- [x] Difficulty setting (Easy, Medium, Hard, Nightmare) chosen in the menu, one highscore table per difficulty,
      bot-checked win-rate bands (`tools/balance.py`, `tests/test_winnable.py`)
- [x] Checkpoints and level select: a finished arc can be started directly, from an overview map of the arcs
      (`states/select.py`, `states/worldmap.py`: fog over the unopened ones); highscores per arc and difficulty
- [x] Level music: one track per arc and one for the bosses (`tools/compose_music.py`, channels 0-2; the effects keep
      channel 3)
- [x] Settings screen: music and sound volume, fullscreen, screen filter (saved in the profile)
- [ ] Initials for highscores
- [ ] A winnability test per level (`PathController` bot in `tests/test_winnable.py`: Classic, The Hunger; input layer, later `pyxel-mcp` once the upstream GitHub account is restored)
- [ ] `snake-quest` 0.x on PyPI
