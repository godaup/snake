# Arc 7: The Workshop: design

Levels 31–35. The theme is **puzzles**: Sokoban for snakes. Each level is a chain of rooms, and each room is a puzzle
with one solution or a few, where the order of moves matters more than quick steering. The arc builds on what exists:
- The airlock doors (terrain that opens and shuts, `map.dig`/`map.fill`, the bot's caches starting over).
- The portals' colour pairs (one colour links things across the level).
- The hunters biting the tail (`CHUNK`), the thorns cutting it, and shots wounding the body.
- The ice drift and the planets' pull, which the bot's arcs simulate (the belts are a third force of that kind).

It adds one mechanic per level:

| #  | Level                     | New mechanic                                                      | Goal           | Weapon  |
|----|---------------------------|-------------------------------------------------------------------|----------------|---------|
| 31 | Crates                    | the head pushes crates; plates open gates of their colour         | reach the exit | –       |
| 32 | Pressure Plates           | the body holds plates down too: grow long enough to hold several  | reach the exit | –       |
| 33 | Keys                      | keys ride in the body as segments and open locks; mice steal them | reach the exit | –       |
| 34 | Conveyors                 | belts carry crates and the snake; levers reverse them             | reach the exit | –       |
| 35 | **Boss: The Clockwork**   | a machine opened only by jamming, holding and unlocking it        | defeat the boss | gun, homing |

The ramp:
- 31 teaches pushing on its own (a short snake, nothing that hunts it);
- 32 makes the snake's length a tool (a timer it lays on the floor);
- 33 makes the body something to protect (keys can be lost);
- 34 adds movement the snake doesn't control;
- 35 asks for all four, under pressure, with a gun.

Timing matters less than in earlier arcs: no level but the boss has a time limit at medium. Difficulty comes from the
puzzles, and the difficulties change speed and pressure, not the puzzles (see each level).

## The rules that make Sokoban work for a snake

The snake never stops, turns in about a tile and needs about two to turn round (1.3 px per frame at 24 fps, 9° per
frame). Sokoban needs a pusher that can stop, back off and line up. These rules bridge that gap; every level uses them.

- **The bench grid.** Workshop levels are laid out in 16 px cells (2×2 tiles): walls, plates, gates and crates all sit
  on it. A one-cell lane is wide enough to pass but not to turn round in, so lanes are one-way decisions; rooms are
  at least three cells wide where the snake must turn.
- **Pushing.** A `Crate` (16×16 entity) that the head runs into moves along the axis nearest to the snake's heading,
  keeping just ahead of the head: it moves as far along that axis as the head does. When the head leaves it (turns
  off its face), the crate glides on to the next cell, so it always comes to rest on the grid. A crate only moves along
  the grid's axes, so it never leaves its row or column sideways.
- **A blocked crate is a buffer, not a wall.** If a crate can't move (a wall, another crate, a shut gate, the snake's
  body or an entity in the way), the snake **stalls**: it stands still, steering turns it on the spot, and it moves on
  once its next step no longer runs into the crate, which means turning about 90° and sliding along the crate's face.
  This is the only place in the game where the snake stops, and it is what makes lining up possible: push a crate into
  a corner, stall, turn, go round. Walls still kill: running into a wall beside a crate is a crash.
- **Plates and gates.** A plate (terrain, in one of three colours) is down while a crate rests on it or any part of the
  snake lies on it. A gate (terrain, the same colours) is open while every plate of its colour is down. A gate never
  shuts on the snake or a crate: it stays open until nothing lies in it. Colours link plates and gates anywhere in the
  level, like portal pairs.
- **The reset lever.** Each room has one (terrain, painted by the designer). The head crossing it puts the room's
  crates back where they started (a room is the area between gates, found by a flood fill that counts gates as walls).
  A crate whose start is covered waits until it is free. Sokoban needs an undo, and this is it, without a menu.
- **Gates and the body.** The snake's length decides how long it holds a plate: a body `n` segments long covers a spot
  for about `n × 1.3 px / speed` after the head has passed it. That is the puzzle of level 32. In level 31 the snake is
  too short for it (10 segments, 13 px), and the plates lie far enough from their gates.

## Look, sound, map

- **Resources:** `arc7.pyxres`, tilemaps 0–4.
- **Layouts** come from text. A new `tools/draft_workshop.py` reads a puzzle in Sokoban-like notation (one character per
  16 px cell) and writes the tilemap, with walls as `WALL_TILE` blocks so the autotiler draws them:

  ```
  ##########
  #@  #  r E#      @ start   # wall   $ crate   r/b/y plate   R/B/Y gate   1/2/3 lock (red/blue/yellow)
  #  $#   ###      k/K/L key (red/blue/yellow)   > v < ^ belt   s belt lever   x reset lever   a apple
  #x  R     #      E exit   m mouse   * thorns
  ##########
  ```

  The text files live in `tools/puzzles/<level>.txt` and are the source of truth for the layouts, like the maze's
  draft (`draft_maze.py`). `tools/solve_workshop.py` reads the same files and solves the crate rooms (see Bot).
- **Walls:** the hedge autotiles drawn as brass and copper with `tint: {3: 4, 11: 10}`. The floor is dark (colour 1)
  with a faint cell grid as decor, so the bench grid shows.
- **Light:** every level is lit: puzzles need to be seen whole. Rooms are sized to fit the play area (at most 40×26
  tiles of floor each), so a whole room is on screen at once.
- **Music:** a new `workshop` track in `tools/compose_music.py`, sounds 37–39. Pyxel has only 8 music slots and all are
  taken (0, 2–7 the levels, 1 the theme). `SoundManager.play` starts each channel itself and uses a music only as the
  list of sounds per channel, so tracks beyond the slots become plain sound lists: `sound.MUSIC` maps a name to a slot
  or to its sounds (`"workshop": (37, 38, 39)`), and `play`/`_gain` read either.
  - mechanical and busy, C Mixolydian, about 120 bpm;
  - a plucky pulse lead in staccato eighths, a walking triangle bass, a ticking hat on every eighth (the clock) and a
    noise "woodblock" on the offbeats;
  - quieter than the battle tracks, since you think while it plays; the boss level uses `music: boss`.
- **Overview map:** the arc's `map` theme in `campaign.yaml`: ground colour 1, the brass tint, props crates and cogs,
  boss sprite the Clockwork's 16×16 icon.

### New sprites (bank 0)

Row 10 is full in columns 0–15, so the new terrain goes into its columns 16–31 (the image is 32 tiles wide), and the
entities into row 21 on:

| Sprite                       | Tile(s)              | Notes                                                     |
|------------------------------|----------------------|-----------------------------------------------------------|
| Plate red / blue / yellow    | (16–18, 10)          | terrain, floor; drawn pressed (darker, a shadow) while down |
| Gate shut red / blue / yellow | (19–21, 10)         | terrain, a wall                                           |
| Gate open red / blue / yellow | (22–24, 10)         | terrain, floor (bars drawn in the floor)                  |
| Lock red / blue / yellow     | (25–27, 10)          | terrain, a wall; unlocked, it becomes the open gate tile  |
| Belt right / down / left / up | (28–31, 10)         | terrain, floor; moving chevrons drawn over it by code     |
| Belt lever, flipped          | (0, 21), (1, 21)     | terrain, floor                                            |
| Reset lever                  | (2, 21)              | terrain, floor                                            |
| Workshop floor grid, oil spot | (10, 9), (11, 9)    | floor decorations (`DECOR_TILES` grows to 12)             |
| Crate                        | (3, 21)–(4, 22)      | 16×16 entity                                              |
| Key                          | (5, 21)              | pickup, drawn in its colour with `pal`                    |
| Clockwork mouse              | (6, 21), (7, 21)     | two frames (wound, running)                               |
| The Clockwork                | (8, 21)–(11, 24)     | 32×32; its hands drawn as lines; icon (12, 21)–(13, 22)   |

A gate's or lock's colour is in its tile, so the editor shows what links to what. Every new terrain tile goes into
`TILE_KINDS` and `TERRAIN_TILES`; shut gates and locks into `WALL_TILES`.

## Level 31: Crates

> The Workshop's doors are worked by plates. Push the crates onto them. Stuck? Cross the lever to start the room again.

**Mechanics:** pushing, stalling, plates and gates, the reset lever (all above).

**Entity** `Crate` (`crate`, (3, 21), 16×16, not hostile, `solid`):
- `start`: its cell when the map loaded (for the reset lever); `cell`: where it rests; `push(axis, px)` and `glide`.
- It isn't eaten, can't be shot (shots stop at it, like at a wall) and never hurts the snake.
- Hunters, mice and drones treat it as a wall; asteroids don't occur here.

**Level** (`crates.yaml`, tm 0, about 1280×416, four rooms in a row, the exit in the last):
1. One crate, one red plate, the red gate: push it straight on. Teaches the push.
2. A crate in a one-cell lane with the plate at the end, and a second crate that must go first, out of the lane's
   mouth. Teaches the stall: the first push ends against a wall.
3. Two crates, two blue plates in a corner pocket: the order matters (the wrong one first blocks the other).
4. Three crates, one red and two yellow plates, the yellow gate in front of the exit and the red one on the way.
- Snake length 10; no apples and no enemies; a reset lever in every room.
- Goal `exit: true`.
- Difficulty: the snake's speed scales as usual (faster is harder to line up); hard and nightmare add a `time_limit`
  in overrides (generous: about twice the bot's median).

**Bot:** follows the level's plan (see Bot, below).

## Level 32: Pressure Plates

> Some doors need more plates than you have crates. You are long enough to lie on them yourself, if you eat.

**Mechanic:** the body presses plates (the same rule as in 31, but now the snake is long enough to use it):
- A plate is down while any segment lies on it (`map.update` marks the plates the body covers each frame, a set of
  tiles from the segments' positions: cheap, since the body is a few hundred px at most).
- A gate that needs three plates of its colour is opened by laying the body across all three at once, or two and a
  crate. The route over the plates and on to the gate has to fit within the snake's length: the head must be in the
  gate before the tail leaves the first plate (after that, the gate stays open while the body passes, see the rules).
- Apples grow the snake (`+5`), and growing is the way to open the bigger gates.

**Level** (`plates.yaml`, tm 1, about 960×640, a hub with three wings):
- Each wing holds a gate needing 1, 2 or 3 plates and the apples to grow long enough for it.
- The last wing mixes: two plates for the body, one for a crate that must be pushed there first.
- A little thorn patch beside one plate: cutting the tail shortens the hold (a lesson for 33).
- Goal `exit: true`; start length 10, apples by timer (`max: 3`).
- Difficulty: speed as usual; hard and nightmare give fewer apples on the map at once (`max` in overrides) and a
  `time_limit`.

**Bot:** the plan names the plates to cross in order and the gate; the bot grows first (the plan's `grow` step: eat
until `length` is reached), then drives the route.

## Level 33: Keys

> Keys ride in your body. Keep them deep: the mice bite tails, and a bitten-off key falls to the floor.

**Mechanic: key segments.**
- A key pickup (`key`, (5, 21), red, blue or yellow: the colour is the tile it was painted from, or `with: {COLOUR:
  ...}` for spawned ones) adds one segment at the tail that carries it (`segment.key = colour`), drawn as a key in the
  body.
- As the snake grows, new segments are appended behind it, so the key moves deeper into the body (the same index from
  the head, more segments behind it).
- The head touching a lock (terrain, a wall) of a colour the body carries opens it for good (it becomes that colour's
  open gate tile, `map.dig`-like, so caches start over), and that key's segment is removed (the body closes up).
  Without the key, a lock is a wall like any other: a crash.
- Losing keys: whatever cuts the tail (a hunter's bite, thorns, a hostile shot's wound, a closing airlock door) drops
  the keys in the cut part onto the floor where they were, as pickups again.

**Entity** `Mouse` (`mouse`, (6, 21), a `Hunter` subclass, hostile):
- Clockwork mice wind up (asleep, eyes closed sprite) and run; they hunt the **deepest key segment**, not the tail
  (`map.chase` from that segment instead: a second shared field, refreshed like `map.chase`).
- A bite cuts the body behind the segment it bites (so the key falls off with the cut part), `CHUNK` limited as for
  hunters; no key in the body: they hunt the tail.
- One health; the snake can't shoot here, so they are avoided, outrun or led over thorns (mice die on thorns).

**Level** (`keys.yaml`, tm 2, about 1024×640):
- Three locked doors in a row of rooms, keys behind other locks (yellow behind red, blue behind yellow), and one room
  that has two keys of which only one fits a lock you can still reach (the other is a lure into a mouse nest).
- Apples throughout (to bury the keys), thorn patches on the short ways, a few mouse holes (`Nest` sprites reused,
  spawning `mouse`).
- Goal `exit: true`.
- Difficulty: mice spawn with the `hostile` factor; hard and nightmare add one mouse hole and a `time_limit`.

**Bot:**
- The plan: `key` steps (fetch) and `unlock` steps (a lock to touch).
- New target rule: while the body carries a key, grow (eat) before going near mice if the key is within `KEY_DEPTH`
  segments of the tail.
- Locks without a matching key are walls in its way-finding; with one, the lock is a target.
- Threats: mice as hunters, which it already keeps away from.

## Level 34: Conveyors

> The belts never stop. They carry crates, and they carry you. Throw a lever to turn them round.

**Mechanic: belts.**
- A belt tile (terrain, floor, four directions) moves what lies on it by `BELT` px per frame (0.6 at medium, less than
  the snake's 1.3): the head is shifted each frame it is on one (the body follows the head's path, as always), so going
  with a belt is fast, against one slow, and across one drifts.
- Crates on belts are carried along until blocked, and they come to rest on the cell where the belt ends or where
  they are stopped (they glide to the grid as after a push). A carried crate that a shut gate blocks waits at it.
- A belt lever (terrain, flips between two tiles) reverses every belt in its room (the room as for the reset lever)
  when the head crosses it. The levers are the puzzle: route crates onto plates by reversing belts at the right time.
- `map.drift_at(pos) -> Vec2` gives the belt's push at a point; `snake.update` adds it to the head's step, and the
  bot's arcs simulate it (like `map.pull`). The chevrons are drawn by code, moving in the belt's direction.

**Level** (`conveyors.yaml`, tm 3, about 1280×640):
1. A belt loop carrying a crate round: throw the lever as it passes the plate's spur.
2. Belts in a cross with two crates; one lever turns all of them, so the crates swap places.
3. A belt lane against you to the exit: ride the return belt round, or go slowly against it.
- Apples, no enemies.
- Goal `exit: true`.
- Difficulty: `BELT` scales with the speed factor (in `with:` overrides per difficulty, as `grip` does); hard and
  nightmare add a `time_limit`.

**Bot:** the plan has `lever` steps (cross a lever) and `wait` steps (until a crate rests on a cell or a gate opens).
Its arcs include the belts' drift.

## Level 35: Boss: The Clockwork

> The Clockwork winds the whole Workshop. Jam its gears, hold its springs, open its locks, then break its heart.

**Boss** `ClockworkBoss` (`clockwork`). A 32×32 `Clockwork` entity sits in the middle of a round arena (walls and
gates on the bench grid). It has two hands, a long and a short one (120 and 80 px), that tick round it a step every
second (`tick`: degrees per tick). A hand sweeping over the body cuts it there; one sweeping into the head is the end.
Its face (the core) is shut, so shots glance off, except while it is open. Three phases, by `below`:

1. **Jam the gears (above 2/3).**
   - Four red plates sit at the face's sides, one cell out; four crates are about the arena, each in line with a
     plate.
   - With all four plates down, the gears jam: the hands stop, the face opens for `open` seconds, and shots hurt it.
   - Then it shakes the crates off (`kick`: each is pushed straight out `kick` cells along its axis, so it lies in line
     with its plate again, on the other side if a wall is in the way).
2. **Hold the springs (above 1/3).**
   - The hands tick faster. A ring of six blue plates lies two cells out round the face; the face opens while `hold`
     of them are down.
   - Only the body can hold them (the crates are gone, swept to the wall): coil round the Clockwork and shoot.
   - Homing pickups appear (shots that turn towards it while the snake circles it).
3. **The locks (below 1/3).**
   - It winds itself shut behind three locks (red, blue, yellow) on its face. A conveyor ring round the arena carries
     keys in from a hatch, and a lever reverses it.
   - Clockwork mice pour out (`call`, up to `mice`) and go for the keys in the body.
   - All three locks opened: the face opens for good, and the last hits finish it.
   - The phase message is "THE CLOCKWORK WINDS DOWN... AND UP".

**Boss settings:**
- `pressure`: `health`, `tick`, `mice`;
- `relief`: `open`, `call`, `hold` (fewer plates to hold is easier: `hold` is divided);
- `bar()`: its health;
- `target()`: its face while it is open, else `None` (the bot works the phase's puzzle then, see below);
- `danger()`: circles along each hand where it will be after its next tick, so bots stay off the hands.

**Level** (`clockwork.yaml`, tm 4, 640×640, the arena):
- guns at the start, homing pickups in phase 2, apples (the body must be long for phase 2);
- goal `boss: defeated`, `music: boss`.

**Bot:** the boss has no fixed plan, since the crates and keys move. Its target rules per phase:
- Phase 1: the plate whose crate is closest to it; the crate is in line with its plate, so the push is one straight
  push from the outside (an approach point two cells behind the crate, then the plate).
- Phase 2: a loop of points over the blue plates (the bot's `orbit` targets), firing when its homing shots can reach.
- Phase 3: the nearest key on the belt, then the lock of its colour.

## Bot

Puzzles are the one thing the bot can't find by steering towards the nearest apple. Each level file gets a **plan**:
the steps of a solution, which only bots read.

```yaml
plan:
  - push: [[5, 3], right, 2]  # the crate on cell (5, 3), two cells to the right
  - push: [[8, 3], down, 1]
  - visit: [14, 3]            # a cell to cross: a plate, a lever, a gate
  - grow: 30                  # eat until 30 long
  - key: blue                 # fetch the nearest blue key
  - unlock: [20, 6]           # touch the lock on cell (20, 6)
  - lever: [11, 9]
  - wait: {crate: [12, 4]}    # until a crate rests on cell (12, 4); or {gate: red}
  - exit
```

- `bot.target` gains a plan rule ahead of the others: `map.plan` (from the level file, the current step and what it
  needs) gives a point, and the step is done when its condition holds (the crate on its cell, the cell crossed, the
  length reached, the key carried, the lock open). The rules for apples, threats and weapons stay underneath, so the bot
  still eats and dodges between steps (`grow`).
- A push is three targets in turn: an approach point two cells behind the crate (on its axis), one cell behind, and then
  a point beyond the crate's goal cell; the bot turns off once the crate has passed the middle of its goal cell (it
  glides on to the cell). A push that ends against a wall stalls, and the bot turns along the crate's face.
- Crates are walls in its way-finding (`map.blocked(cell)`, which the distance field consults like walls) except the one
  it is pushing.
- A step that doesn't come true within `PLAN_PATIENCE` seconds: the bot crosses the room's reset lever and starts the
  room's steps again (the plan marks where rooms start).
- `tools/solve_workshop.py` is a plain Sokoban solver (breadth-first over crate cells, the pusher's reach ignoring its
  body) for the crate rooms in `tools/puzzles/`. It finds the shortest number of pushes and writes them as `push`
  steps, so plans for crate rooms aren't written by hand, and a test checks every room is solvable.

Win rates are as relative as ever: the bot reads the solution, people find it. The bands are the same.

## Engine work, in order

1. **Terrain:** plates, gates, locks, belts, levers and the reset lever in `tiles.py`; `map.plates` (colour -> tiles,
   which are down), `map.gates`, rooms by flood fill, `_step_on_tiles` for levers.
2. **Crates and the stall:**
   - the `Crate` entity (push, glide, blocked);
   - `snake.update` asks the map whether the head's next step runs into a blocked crate (`map.stall(head, step)`), and
     if so doesn't move, only turns;
   - `map.blocked(cell)` for the bot's field, hunters and spawning.
   Needed by 31, 32, 34, 35.
3. **Body on plates:** the segments' tiles each frame. Needed by 32, 35.
4. **Keys:** `segment.key`, pickups, locks, keys dropped by cuts (`snake.cut`, `snake.wound`, door cuts all go through
   one place that drops them); the `Mouse` and its key-chasing field. Needed by 33, 35.
5. **Belts:** `map.drift_at`, the head's shift, crates carried, levers; the bot's arcs. Needed by 34, 35.
6. **Boss:** `ClockworkBoss` (hands, face, the three phases).
7. **Bot:** the plan rule, pushes, the reset fallback; `tools/solve_workshop.py`.
8. **Tools and content:** `tools/draft_workshop.py`, `tools/puzzles/*.txt`, `arc7.pyxres`, the sprites, the
   `workshop` music, the map theme, `campaign.yaml` arc 7 ("The Workshop").

## Tests

- **Per mechanic:**
  - a pushed crate moves with the head along one axis and comes to rest on the grid;
  - a blocked crate stalls the snake, and turning along its face frees it (no crash, no self-bite);
  - a plate is down under a crate and under the body; a gate opens with all its plates and doesn't shut on the snake;
  - the reset lever puts its room's crates back and leaves other rooms alone;
  - a key adds a segment, growth buries it, a lock opens with the key and removes it, and a cut drops it;
  - a mouse hunts the key segment;
  - a belt shifts the head and carries a crate, and a lever reverses its room's belts;
  - the Clockwork's face opens only when jammed, held or unlocked, and its hands cut.
- **Puzzles:** every room in `tools/puzzles/` is solvable (`solve_workshop.py`), and each level's plan, played by the
  bot, reaches the exit.
- **Per level:** `bot.LEVELS` and the `WIN_RATES` bands (8 seeds).
- **Registry:** the new tiles in `TERRAIN_TILES`, no stray tiles, `test_music` with the `workshop` track.

## Open questions

- **The stall.** It is new to the game: everywhere else the snake can't stop. The alternative is a blocked crate
  being a wall like any other, which makes every push in a one-cell lane deadly and lining up a guess. My
  recommendation: the stall, for crates only.
- **Plans vs. a solver in the bot.** A solver in the bot would let it solve any room, also ones the player changed
  (the boss's kicked crates). But keys, body plates and belts are beyond plain Sokoban. So: written plans for the
  levels, the offline solver to write and check the crate rooms, and simple per-phase rules for the boss.
- **Boulders.** The roadmap's "crates and boulders": a boulder rolls on until it hits something (ice Sokoban). It is
  one more rule; it would fit level 34 next to the belts, or a one-off level. Left out for now.
- **Length in level 31.** Without apples the length is fixed, which keeps the body out of the plates' way. If it feels
  stingy, a few apples in the last room.
