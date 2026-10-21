# Arc 6: Space: design

Levels 26–30. The theme is **oxygen and inertia**: the snake leaves the ground behind. The arc builds on what exists:
- The Hunger's meter that drains and refills, and its shrinking light.
- The ice drift (`snake.grip`, `utils.drift`), which the bot already simulates.
- The drones that fly over walls, the turrets, and the Core's shield and phases.

It adds one mechanic per level:

| #  | Level                     | New mechanic                                         | Goal                    | Weapon         |
|----|---------------------------|------------------------------------------------------|-------------------------|----------------|
| 26 | Airlock                   | oxygen drains; air tanks refill it                   | score                   | –              |
| 27 | Zero-G                    | little grip anywhere: the snake keeps its momentum   | reach the exit          | tractor (new)  |
| 28 | Gravity Wells             | planets pull the snake's heading; slingshots         | collect all stars       | –              |
| 29 | Asteroids                 | the level wraps around its edges; asteroids split    | destroy all asteroids   | gun, spread    |
| 30 | **Boss: The Mothership**  | a ship on an orbit through the wells, dropping raiders | defeat the boss       | gun, spread    |

The ramp follows the earlier arcs:
- 26 adds a meter to manage (pressure, not a killer at first);
- 27 changes how steering feels;
- 28 adds forces you can use;
- 29 changes the shape of the world;
- 30 combines gravity, mild inertia and the arc's enemies.

Every new mechanic is a level option or a goal type, so the boss level (and later levels) can mix them.

## Look, sound, map

- **Resources:** `arc6.pyxres`, tilemaps 0–4.
- **Layouts:** two kinds, both new `draft_garden.py` commands.
  - `station` (26, 27): the corridors and rooms of a space station: rectangular rooms joined by straight corridors
    (wide enough to turn in, at least 5 tiles), an outer hull. Rooms are placed on a grid with a random spanning tree of
    corridors plus a few extra links, so there are loops.
  - `void` (28–30): open space with a thin hull border, or none at all where the level wraps (29), and a few asteroid
    rocks as small walls. The planets are entities, not walls.
- **Walls:** the hedge autotiles drawn as hull plating with `tint: {3: 5, 11: 12}` (dark blue plates, cyan edges).
  - The floor in station levels is black with a faint grid decor.
  - In open space the floor is a starfield: decor tiles on row 9 (small stars, a distant galaxy), drawn but walkable.
    Two new decor tiles: (8, 9) and (9, 9).
- **Light:** Airlock is dark: the suit's lamp is the light (`darkness`), and it shrinks with the oxygen. The other
  levels are lit: space is full of stars.
- **Music:** a new `space` track in `tools/compose_music.py` (`sound.MUSIC["space"] = 7`, sounds 34–36):
  - floating and wide, F Lydian (the raised fourth gives the sci-fi shimmer), about 100 bpm;
  - a square arpeggio lead with vibrato on held notes, a slow triangle pad bass, and sparse hats only;
  - the boss level uses `music: boss`.
- **Overview map:** the arc's `map` theme in `campaign.yaml`:
  - ground colour 0 (black) with the star decor;
  - the hull tint;
  - props planets and asteroids;
  - boss sprite: the Mothership (its 16x16 icon).

### New sprites (bank 0)

Rows 17 and 18 are free, and row 10 has two terrain tiles left:

| Sprite                 | Tile(s)            | Notes                                           |
|------------------------|--------------------|-------------------------------------------------|
| Airlock door (closed)  | (14, 10)           | terrain: a wall that opens (Airlock)            |
| Airlock door (open)    | (15, 10)           | terrain: floor                                  |
| Star decor, galaxy     | (8, 9), (9, 9)     | floor decorations                               |
| Air tank               | (0, 17)            | pickup, refills oxygen                          |
| Star (to collect)      | (1, 17)            | glowing pickup                                  |
| Tractor pickup         | (2, 17)            |                                                 |
| Asteroid (small)       | (3, 17)            | 8x8                                             |
| Asteroid (medium)      | (4, 17)–(5, 18)    | 16x16                                           |
| Asteroid (large)       | (6, 17)–(9, 20)    | 32x32 (rows 17–20)                              |
| Planet                 | (10, 17)–(11, 18)  | 16x16, drawn with a ring of `tint` per planet   |
| Raider                 | (12, 17)           | small ship                                      |
| Engine pod             | (13, 17)           | the Mothership's weak points                    |
| Mothership             | (0, 19)–(3, 20)    | 32x16; its 16x16 map icon at (14, 17)–(15, 18)  |

## Level 26: Airlock

> The station is losing air. Your suit holds a little. Find the tanks, keep breathing.

**Mechanic: oxygen.** A goal type, like `time_limit` and `collapse`: `oxygen: {drain: s, tank: share, light: [R, r]}`.
- The suit holds 1.0 of oxygen, and it drains in `drain` seconds (60 at medium).
- An air tank (`tank` entity, (0, 17)) refills `tank` (0.4) of it, up to full. It is a pickup with `light`, respawning
  like apples (a timer).
- At 0, the level is lost (`map.snake_killed`).
- The suit's lamp shrinks with it, from `light[0]` (64) to `light[1]` (24), like The Hunger's.
- It is always done; the other goals decide the win.
- The footer shows "O2 63%" with a bar that turns red below a quarter, and a beeping warning sound (`hurt` every 2 s
  below 15%).
- Difficulty: `drain` is divided by the goals factor (harder drains faster), `tank` stays.

**Airlock doors** ((14, 10) closed, (15, 10) open) are terrain:
- A closed door is a wall (in `WALL_TILES`). Every `cycle` seconds the station's doors swap, the open ones closing and
  the closed ones opening: `airlock: {cycle: 6, warn: 1}`, a level option, with the doors blinking for `warn` seconds
  before.
- A door closing on the snake's body cuts it there (as the cave-in does); one closing on the head is the end. This
  reuses `map.fill` and `map.dig`, so the bot's caches start over.
- Doors are painted in the editor across corridors, in pairs that alternate (one of each pair open).
- This is the level's second piece. If it is one too many for the first level, Airlock can go without doors, and they
  come back in the boss level.

**Level** (`airlock.yaml`, tm 0, 768×512, `station`):
- rooms and corridors with doors at a few corridor mouths;
- tanks (`max: 2`), apples (3), a few sleeping beetles (the station's pests, from arc 2);
- goal `score: 30`, with `oxygen: {drain: 60, tank: 0.4, light: [64, 24]}`.

**Bot:**
- A new target rule: when oxygen is below a threshold (0.45), go for the nearest tank first.
- Doors: closed ones are walls in the way-finding. The ones about to close (blinking) are walls too, like the cave-in's
  cracks.
- The tanks' respawn timer is the knob for the bands.

## Level 27: Zero-G

> The gravity is off. You keep drifting where you were going; steering only slowly bends your way.

**Mechanic: inertia everywhere.**
- `grip: 0.15` as a level option: `snake.grip` is that everywhere (not only on ice). `Map._step_on_tiles` sets it from
  the level, and ice (if any) sets its own.
- The bot's arcs already simulate drift with `map.ice`. That becomes `map.grip_at(pos)`, so both read the same rule.
- Low grip makes walls the danger: corridors are wide (7+ tiles) and rooms large, and the exit is far.

**New weapon: Tractor** (`tractor` pickup (2, 17), `Tractor` weapon, `AMMO` 20 "charges", `COOLDOWN` 0.1):
- While fire is held it pulls the nearest pickup in a cone ahead (`RANGE` 80 px, `CONE` 25°) towards the head at
  `PULL` px per frame.
- Pickups are apples, tanks, stars and weapons, never hostile entities.
- Every frame of pulling uses one charge. It is drawn as a dotted cyan beam.
- In zero-G it saves risky turns: pull the apple instead of steering for it.
- It counts as a weapon, so picking up a gun drops it, and the other way round.

**Level** (`zerog.yaml`, tm 1, 1024×384, `station` with `--wide`):
- a long station section from the start to an exit at the far end;
- apples along the way, a few drones (they ignore inertia, so they are faster at turning than you), tractor pickups;
- goal `exit: true` and `length: 30` (grow first, then leave, so the pickups matter);
- difficulty: `grip` is set per difficulty in overrides (easy 0.25, medium 0.15, hard 0.12, nightmare 0.1), since there
  is no factor for it.

**Bot:**
- The drift simulation already exists, so steering works.
- Tractor: `fire` while the target pickup is in the cone and in range. `bot.target` is unchanged; the pulling simply
  brings the target closer.
- Expect lower win rates than Ice: tune `grip` and the corridor width.

## Level 28: Gravity Wells

> Planets pull you in. Skim them to swing round; fall in and you burn.

**Mechanic: gravity.**
- A `Planet` entity (16x16, (10, 17); `mass`, `radius` from the level via `with:`) pulls the snake's heading. Every
  frame `snake.heading` turns towards the planet by `mass / distance²` degrees, capped (`MAX_PULL` 4° per frame), within
  `REACH` (120 px).
- Only the heading turns, not the speed: at a constant speed, a pull on the heading is what makes slingshots work in
  this game. Skimming a planet swings the snake round it; flying straight at one is a crash.
- The pull is computed in `map.pull(pos, heading) -> degrees`, so the game and the bot's arcs use the same function.
- Touching a planet (its circle) is a crash, like a wall.
- Planets are entities so they can move: the boss level puts them on slow orbits (`orbit: [cx, cy, r, period]`).
- Shots are pulled too (half as much), so you shoot around planets.
- Drawn as a disc with a ring and a faint dotted circle at `REACH`, so the player sees the pull.

**Stars** (`star`, (1, 17)): glowing pickups that don't respawn; `collect_all: star`. Placed in the tilemap with
`scatter`, many of them in orbit-like spots close to planets.

**Level** (`gravity.yaml`, tm 2, 768×512, `void`):
- 5 planets of different masses, 10 stars, apples;
- no enemies: the planets are the danger;
- a time limit (120 s) so you have to use the slingshots instead of creeping around;
- difficulty: planet masses scale with the boss factor (a `with: {MASS: ...}` override per difficulty).

**Bot:**
- The arcs simulate the pull (`map.pull` per frame). The distance field treats planets plus a margin as walls.
- With the pull in the arcs, the bot finds slingshots by itself where they get it closer to the target.

## Level 29: Asteroids

> The sector wraps around: fly off one edge, come back on the other. Shoot the rocks, and mind the pieces.

**Mechanic: a level that wraps around.** `wrap: true` (a level option):
- **Movement:** the snake's head leaving an edge comes in at the opposite one. Its segments follow, so the body is
  split across the edge for a moment. Every segment's position is kept wrapped, and distances between segments take
  the wrap into account (`map.delta(a, b)`: the shortest vector across the edges).
- **Shots, drones and asteroids** wrap too.
- **Drawing:** `Cam` doesn't clamp at the edges any more. It draws the tilemap and everything in it up to four times
  (offset by the level's width and height) where the view crosses an edge. The level is made exactly as big as a few
  screens (640×448), with no border walls.
- **Collisions** between the head and segments or entities use `map.delta`.
- **Bot:** the BFS field and the arcs wrap (cells modulo the grid). `nearest` measures with `map.delta`.
- This is the arc's biggest engine change: every distance in the game that compares world positions must go through
  the map. `utils.Vec2` stays as it is; the map gains `wrap_pos` and `delta`. Tests guard the edges (a head across the
  edge is still next to its neck; a shot across the edge hits).

**Asteroid** (`asteroid`, small/medium/large: 8/16/32 px; `size` 1–3):
- It drifts in a straight line at `SPEED` (faster when smaller) and spins (drawn rotated by swapping between a few
  frames, or not at all).
- Shot, a large one splits into 2 medium, a medium one into 2 small; a small one is destroyed. The pieces fly apart at
  ±40°.
- `destroy_all: asteroid` counts every piece: `CollectAllGoal` already counts spawned ones as they appear (`seen`).
- Touching one: the head is the end; a small one hitting the body cuts like a drone sting (2 segments), a big one cuts
  at the segment.
- Hostile, `avoid` true for large and medium ones, false for small ones (like drones).

**Level** (`asteroids.yaml`, tm 3, 640×448, `void` without border):
- 3 large asteroids at the start, guns and spreads, apples;
- goal `destroy_all: asteroid`, about 21 pieces in all (3 × (1 + 2 + 4));
- difficulty: more large asteroids on hard (4) and nightmare (5), through a spawn timer in the overrides.

**Bot:**
- It hunts the asteroids like any hostile entity (`nearest` with wrap).
- The aim leads moving targets a little: `_aim` gains the target's velocity if it has one (`vel`), the same intercept
  the turrets use.
- Dodge: asteroids are threats with their velocity, like hostile shots (`_shots` gains entities that move straight).

## Level 30: Boss: The Mothership

> The Mothership circles the sector through the wells, dropping raiders. Break its engines, then hit its core.

**Boss** `MothershipBoss` (`mothership`). A 32x16 `Mothership` entity follows a fixed orbit (a loop through the
level's planets: `path: [[x, y], ...]`, at `speed`), pulled by nothing. It has three phases, by `below`, like the Core:

1. **Phase 1 (above 2/3): engines.**
   - Three `EnginePod`s (turret-like, `HEALTH` 3, (13, 17)) ride on the ship, two at the back, one on top.
   - While any stands, the ship is shielded (the Core's shield, glinting).
   - The pods fire slow hostile shots at the head (`reload`).
   - Each pod destroyed costs the ship a third of a third of its health; three gone ends the phase.
2. **Phase 2 (above 1/3): the bay.**
   - The ship opens its bay: every `call` seconds it drops a `Raider` while fewer than `swarm` are about.
   - Raiders are drone-like ships that fly at the head (`Drone` with a `TURN`) and fire one shot each when lined up.
   - While the bay is open the core is exposed: shots into the bay (the ship's middle 8 px) hurt it.
   - The bay is open for `open` seconds, then closed for `closed` seconds.
3. **Phase 3 (below 1/3): the tractor.**
   - The ship slows, and its tractor beam pulls the snake's heading towards it, like a planet but stronger, within
     `REACH`.
   - Getting close is the way to hit the open core and the way to die (the hull is a wall).
   - The phase message is "THE MOTHERSHIP LOCKS ON".

**Boss settings:**
- `pressure`: `health`, `swarm`, `pull`;
- `relief`: `call`, `reload`, `closed`;
- `bar()`: its health;
- `target()`: a pod while pods stand, then the bay while it is open, else `None` (the bot stocks up on ammo, as for
  the Brood Mother);
- `danger()`: the ship's hull plus a margin, so bots never cut across its path.

**Level** (`mothership.yaml`, tm 4, 960×640, `void`):
- 3 planets on the orbit's corners, with mild grip (`grip: 0.5`: space, but forgiving);
- guns, spreads, tractors, apples, air tanks;
- an `oxygen` goal with a slow drain (120 s), as a reminder of Airlock and not a killer;
- goal `boss: defeated`, `music: boss`;
- overrides: hard health and swarm up, nightmare also less grip.

**Bot:**
- It shoots the pods (the `target()`), dodges raiders and shots as it does drones and turrets, and keeps out of the
  hull.
- In phase 3 its arcs simulate the tractor pull (`map.pull` includes the ship's pull while it is on).

## Engine work, in order

1. **Grip and pull:**
   - `map.grip_at(pos)` (level grip, ice) used by `_step_on_tiles` and the bot's arcs;
   - `map.pull(pos, heading)` (planets, the ship's tractor), applied to `snake.heading` in `snake.update` and in
     `PathController._arc`.
   - Needed by 27, 28 and 30.
2. **Goal and option:**
   - the `oxygen` goal (meter, light, footer);
   - the `airlock` doors (`map.fill`/`map.dig` on a cycle).
   - Needed by 26 and 30.
3. **Wrap:**
   - `map.wrap_pos`, `map.delta`;
   - the snake's segments and collisions, shots, entities, the camera's tiled drawing, the bot's field and arcs.
   - Needed by 29 only, so it can come last or be cut (see the open questions).
4. **Entities:**
   - `AirTank`, `Star`, `Planet` (with orbit), `Asteroid` (split), `Raider`, `EnginePod`, `Mothership`;
   - the `Tractor` weapon and its pickup.
5. **Boss:** `MothershipBoss` (orbit, pods and shield, bay, tractor).
6. **Bot:**
   - the oxygen target rule;
   - door walls;
   - pull in the arcs;
   - wrap in the field and the arcs;
   - leading moving targets;
   - the tractor's fire rule.
7. **Tools and content:**
   - `draft_garden.py station` and `void`;
   - `arc6.pyxres` with five layouts;
   - the sprites above;
   - the `space` music;
   - the map theme;
   - `campaign.yaml` arc 6.

## Tests

- **Per mechanic:**
  - oxygen drains, tanks refill, empty is the end, and the light shrinks;
  - doors cycle, and a closing door cuts the body;
  - low grip drifts everywhere;
  - a planet turns the heading by the expected amount, and the bot's arc and the snake agree frame by frame;
  - wrap: the head crosses an edge and keeps its body joined, shots and asteroids cross too, and `map.delta` is the
    shortest way;
  - asteroids split into the right pieces and `destroy_all` counts them;
  - the tractor pulls pickups only;
  - the Mothership's shield holds until the pods are gone, the bay opens and closes, and the tractor phase pulls.
- **Per level:** `bot.LEVELS` and the `WIN_RATES` bands (8 seeds), as in arcs 4 and 5.
- **Registry:** new entities and tiles, no stray tiles, and `test_music` with the `space` track.

## Open questions

- **Wrap-around is costly.** It touches distances everywhere (collisions, the bot, the camera). A cheaper Asteroids:
  no wrap, a large sector with a border, the asteroids bouncing off it. The level keeps its splitting rocks, but loses
  the classic feel. My recommendation: build 26–28 and 30 first, then decide on wrap with the engine in front of us.
- **Airlock's doors are a second mechanic.** Keep them, or move them to the boss level (where the Mothership could seal
  the sector's doors) and keep Airlock about oxygen alone?
- **The finale.** With six arcs, should Ouroboros (the rival snake) move to the end as the campaign's last boss? It
  would make the story arc "everything at once" again; the Mothership would then be arc 6's boss as planned, and The
  Brood Mother stays arc 5's.
- **Zero-G controls.** A "brake" would make low grip fairer, but the game has only steer and fire. The Tractor uses
  fire; a brake could be "fire with no weapon", but that is hidden. Probably no brake: wide corridors instead.
