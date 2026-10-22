# Arc 4: The Caves: design

Levels 16–20. The theme is **darkness and digging**: the cave is dark, and it changes while you play. Walls get dug
away, tunnels cave in, and webs close passages. The arc builds on what exists: `darkness` (The Hunger), hunters, the
`trail` bookkeeping (tiles that change and change back), the Core's shield and Turret's warning glow. It adds one
mechanic per level, as the ground rules say:

| #  | Level                      | New mechanic                                   | Goal                         | Weapon        |
|----|----------------------------|------------------------------------------------|------------------------------|---------------|
| 16 | Webs                       | spiders spin webs that hold the snake          | collect all crystals         | –             |
| 17 | Moles                      | moles dig through the walls (the map changes)  | defeat N moles               | gun           |
| 18 | Collapse                   | a cave-in chases the snake through a long cave | reach the exit               | –             |
| 19 | Bats                       | bats wake in the light; the **Flare**          | survive N seconds            | flare (new)   |
| 20 | **Boss: The Brood Mother** | a giant spider drops from the dark ceiling     | defeat the boss              | flare, gun    |

The difficulty ramps the way the earlier arcs do: 21 adds a hindrance (not a killer), 22 adds a map that changes, 23
adds time pressure, 24 adds deep darkness and a new weapon, and 25 combines them.

## Look, sound, map

- **Resources:** `arc4.pyxres`, tilemaps 0–4, like the other arcs.
- **Layouts:** a new `draft_garden.py cave` command: a cellular automaton (random fill, then a few smoothing passes)
  carves organic caverns, which are then joined by tunnels (each cavern to its nearest, so everything is reachable).
  It has the same options as the other commands (`--seed`, `--open X Y R` for the boss arena), plus `--fill` (rock
  share, about 0.45) and `--passes` (smoothing, about 4). Collapse uses `--long` instead: one winding tunnel with
  side caverns, 1536 px long.
- **Walls:** the hedge autotiles drawn as rock with `tint: {3: 4, 11: 9}` (brown and orange edges), as the Fortress
  draws stone. The floor is dark, `floor: 1` under darkness, and decorated with pebbles and moss.
- **Darkness:** every level is dark, but less than The Hunger at first: lights of about 72 px in Webs, 56 in Bats.
  Crystals, mushrooms and flares glow. The difficulty's `light` factor applies as usual.
- **Music:** a new `caves` track in `tools/compose_music.py`, written into the free sounds after 30 and
  `sound.MUSIC["caves"] = 6`.
  - It is slow (about 80 bpm) and in D Dorian: a plucked pulse lead with long fades, like dripping water.
  - The bass is a triangle drone on D and A, and the drums are sparse high noise "drips" with an occasional low thud.
  - It is quieter than the other tracks, to keep the dark tense. The boss level uses `music: boss`.
- **Overview map:** the arc's `map` theme in `campaign.yaml`:
  - ground colour 4 (brown);
  - the rock tint;
  - decor crystals and mushrooms, props stalagmites;
  - boss sprite: the Brood Mother.

  The region is the first one behind the fog after Ouroboros.

### New sprites (bank 0)

The tiles below are free (rows 10, 11 and 12 have room, row 15 and below are empty):

| Sprite                     | Tile(s)            | Notes                                      |
|----------------------------|--------------------|--------------------------------------------|
| Web                        | (10, 10)           | terrain: grey strands on the floor         |
| Torn web                   | (11, 10)           | terrain: the web after it held the snake   |
| Rubble                     | (12, 10)           | terrain: a wall (in `WALL_TILES`)          |
| Cracked ceiling (warning)  | (13, 10)           | terrain: floor with falling dust           |
| Spider                     | (0, 15), (1, 15)   | two walking frames                         |
| Crystal                    | (2, 15)            | glowing pickup                             |
| Mole mound                 | (3, 15)            | underground: a moving heap of earth        |
| Mole                       | (4, 15)            | surfaced                                   |
| Bat                        | (5, 15), (6, 15)   | hanging (asleep), flapping                 |
| Flare pickup               | (7, 15)            |                                            |
| Spiderling                 | (8, 15)            |                                            |
| Egg sac                    | (9, 15)            | nest-like, glows faintly                   |
| Glow mushroom              | (10, 15)           | decor that glows (an `Entity` with `light`) |
| Brood Mother               | (12, 15)–(13, 16)  | 16x16                                      |

## Level 16: Webs

> Spiders spin webs across the dark tunnels. Touch one and it holds you for a moment.

**Mechanic: webs.**
- `WEB_TILE` (10, 10) is a new `TileKind.WEB`: walkable, but nothing spawns on it.
- When the head enters a web tile, `Map._step_on_tiles` holds the snake: `snake.boost(WEB_SLOW, WEB_HOLD)` (0.35×
  speed for 1.2 s; `boost` already handles a factor and a duration, and a new boost replaces the old one).
- The tile then becomes `TORN_WEB_TILE` (11, 10), which no longer holds.
- After `WEB_REGROW` (8 s) the tile is a web again, unless something lies on it. This reuses the `map.trail`
  bookkeeping: a dict from tile to [the tile it covers, seconds left].
- Webs can be painted in the editor or spun by spiders.

**Spider** (`spider`, (0, 15), hostile, `HEALTH` 1):
- It walks along the walls: it keeps to floor tiles next to walls and turns at corners, a wall follower that
  goes left or right at random.
- Every `SPIN` s (3 s, times the `hostile` factor) it leaves a web on the tile it is on, at most `WEBS` (6) of its own at
  a time. The oldest disappears first.
- It does not hunt. Touching it costs `BITE` (3) segments, and it scuttles away for `RETREAT` s.
- It is not shot at in this level, because there is no gun.

**Crystal** (`crystal`, (2, 15)):
- A glowing pickup (`light` 20 px) worth 3 points and 2 segments.
- It doesn't respawn; the goal is `collect_all: crystal`.

**Level** (`webs.yaml`, tm 0, 768×512):
- a cave with 8 crystals in side caverns and webs painted at narrow passages;
- spiders spawn every 10 s, `max: 5`;
- apples (they glow, as in The Hunger);
- `darkness: {light: 72, floor: 1}`.
- The intro teaches the web ("webs hold you; spiders spin new ones").

**Bot:**
- Web tiles get a cost in the BFS field: `WEB_COST`, about 6 cells, so it goes round a web when the detour is short and
  through it otherwise. The BFS becomes a cheap Dijkstra (0-1-k buckets) only where webs exist; levels without webs
  keep the plain BFS.
- Spiders are threats like awake hunters.

**Tuning knobs:** `WEB_HOLD`, spider count and `SPIN` (`hostile`), the crystal count (fixed in the tilemap). Hard and
nightmare overrides add spiders and webs.

## Level 17: Moles

> Something digs beneath the cave. Moles break through the walls, and the hunters use their tunnels.

**Mechanic: digging (a map that changes for good).**
- `Map.dig(tile)` turns a wall tile into floor and re-autotiles its neighbours (`_autotile_walls` for a 3×3 area).
- It bumps `map.walls_version`, which tells everything that cached walls to throw the cache away:
  - `PathController._wall_cache` (only permanent walls are cached since Trail);
  - `map.chase` and `map.flight`;
  - breadcrumb distances.
- Digging never opens the map's outer border.
- This is the engine piece Collapse and the boss need as well; `Map.fill(tile, RUBBLE_TILE)` is its opposite.

**Mole** (`mole`, mound (3, 15), surfaced (4, 15), hostile, `HEALTH` 1, `tally` true):
- **Underground** (a mound): it moves at `SPEED` 0.8 through floor and walls alike, towards a random spot about
  `REACH` tiles away. It digs every wall tile it passes (`map.dig`), leaving a tunnel. Shots pass over it, and it
  can't be hurt.
- **Surfaced**: every `SURFACE` s (5 s, times `hostile`) it comes up on floor for `UP` s (1.5 s, the window to shoot
  it), looks about, and goes down again.
- Running into a surfaced mole costs `BITE` segments.
- At most `DIG_LIMIT` wall tiles per mole (60), so the cave never becomes one open hall.

**Level** (`moles.yaml`, tm 1, 640×448):
- caverns with thick rock between them, so moles open shortcuts;
- hunters (arc 2) sleep in the far caverns and use the new tunnels (`map.chase` is recomputed when the walls change);
- guns, apples;
- goal `defeat: 6` (only kills count, as always).
- Darkness light 80: you see a mound before it surfaces, by the dust it throws.

**Bot:**
- It waits near a mound and shoots when the mole surfaces: `Mole` is a foe only while surfaced, so `nearest` skips
  underground moles via a `targetable` property.
- `bot.target` moves it towards the nearest mound while it has ammo, and the aim needs the 1.5 s window. Expect a lower
  win rate than Armed; tune `UP` and `SURFACE`.

## Level 18: Collapse

> The cave is coming down. Run.

**Mechanic: the cave-in front.**
- `collapse: {speed: px/s, start: s, warn: s}` in the level file.
- After `start` s (5 s, so the snake gets going) a front moves along the cave at `speed` px/s (about 24: the snake
  makes about 31 px/s, `INIT_SPEED` 1.3 px per frame at 24 fps, so wasted turns cost ground).
- Tiles within `warn` s of the front show `CRACK_TILE` (dust falling), and then they become `RUBBLE_TILE` walls.
- The front follows the cave's path, not a straight line: it is a breadth-first distance from the start position
  (the same field `map.chase` uses). Every tile whose distance is below `front` is rubble. So side caverns fill in
  as well, and dead ends are deadly.
- Being caught (the head on rubble) is a wall crash. The body's segments caught in it are cut off
  (`snake.cut`): a long snake loses its tail rather than dying, but the head must stay ahead.
- The camera shakes slightly near the front (a new `cam.shake(px)`).
- The HUD footer shows the distance to the front as a goal-like bar (`CollapseFront.status()` "CAVE-IN 12m").

**Level** (`collapse.yaml`, tm 2, 1536×256):
- one long winding tunnel (`draft_garden.py cave --long`) with side caverns holding speed apples and goldens: risk
  against reward;
- a few webs from level 16 at bends (they hold you while the cave comes down);
- goal `exit: true` at the far end;
- darkness light 80.

**Difficulty:**
- `speed` scales with the `boss` factor (`pressure` key, like a boss), and `start` with `relief`.
- Overrides for nightmare lower `warn`.

**Bot:**
- Rubble is a wall.
- The crack tiles get a high BFS cost, so it never goes back into the warning band.
- `bot.target` is the exit.
- The side caverns are tested: the bot takes them only when the front is far enough behind (`map.collapse.margin(pos)`
  says how many seconds a detour can take).

## Level 19: Bats

> Deep in the cave, bats hang asleep. Your light wakes them.

**Mechanic: bats that wake in the light.**
- `Bat` (`bat`, hanging (5, 15), flying (6, 15), hostile, `HEALTH` 1, `avoid` false like drones: swerving round a
  flock costs more than a bite) hangs asleep on the ceiling (any floor tile next to a wall).
- It wakes when it lies inside any light: the snake's light radius, a crystal's, or a flare's. The test is the same as
  the darkness renderer's: distance to each light source below its radius.
- Awake, it flutters in a jittery flock: boids-lite, steering to the snake plus random jitter, flying over floor only.
  It bites `BITE` (2) segments and flies off for `RETREAT` s.
- After `ROOST` s without seeing light it goes back to sleep on the nearest ceiling tile.

**New weapon: Flare** (`flare` pickup (7, 15), `Flare` weapon, `AMMO` 4, `COOLDOWN` 1.0):
- It fires a slow, short shot that stops on the floor after `LIFETIME` and burns for `BURN` (6 s) as a light
  (`light` 48).
- Bats flee from a burning flare instead of the snake: `scare` radius, flight away like `Critter`.
- It also burns webs and egg sacs it touches (Webs, the boss). It deals 1 damage on hit.
- The design question: the snake's own light wakes bats, but a flare thrown ahead scares them away, so you light the way
  before you go.

**Level** (`bats.yaml`, tm 3, 640×512):
- many roosts along the walls;
- `darkness: {light: 56}`;
- crystals as optional bonus points, though their glow wakes the bats roosting near them;
- flares in pickups, apples;
- goal `survive: 75`.

**Bot:**
- Throw a flare ahead (`fire` when sleeping bats are within flare range ahead and none is burning there).
- Keep to dark paths: a small BFS cost for tiles near roosts.
- Bats are threats while awake. Expect to tune this; the bot only needs to be relatively good (the band tests).

## Level 20: Boss: The Brood Mother

> The Brood Mother waits in the dark. When the light goes out, look up.

**Boss** `BroodMotherBoss` (`brood`), a 16x16 `BroodMother` entity (12, 15), `health` 12, `armored` against shots
while she hangs in the dark (shots glance off).

She works in three phases (by `below`, like the Alpha and the Core).

1. **Phase 1 (above 2/3): egg sacs.**
   - She hangs in her lair (a dark cavern, `pos`), unreachable behind webs.
   - `sacs` egg sacs (4; nest-like, `HEALTH` 2, they glow) around the cave each send a spiderling every `call` s while
     the snake is near.
   - Every sac destroyed (shot or burnt by a flare) hurts her (`sac_damage`).
2. **Phase 2 (above 1/3): the drop.**
   - She climbs into the ceiling: she is drawn only as two eyes in the dark.
   - Every `drop` s (6 s, times `pressure`) she drops onto the snake's head: a shadow circle grows for `warn` s
     (1.5 s), like the turret's glow, at where the head will be (`intercept`).
   - Then she lands: crushed if still there (half the body, as a turret's hit to the head).
   - She stays down, stunned, for `stun` s (2.5 s), the only time shots hurt her. Then she climbs back.
   - She webs the tunnels shut (lines of web tiles across passages) every few drops.
3. **Phase 3 (below 1/3): the dark.**
   - The cave's light shrinks (`lights` key, like The Hunger: from 56 to 40 px).
   - The drops come faster.
   - Spiderlings hatch from where she lands.
   - The phase message is "THE BROOD MOTHER SHROUDS THE CAVE".

**Boss settings:**
- `pressure`: `drop`, `call`, spiderling `pack`;
- `relief`: `stun`, `warn`;
- `bar()`: her health;
- `target()`: an egg sac while sacs stand, else her (when stunned) or `None`.

**Level** (`brood.yaml`, tm 4, drafted with `--open` for the arena):
- flares and guns, apples;
- goal `boss: defeated`;
- `music: boss`;
- overrides: hard health 14, nightmare 16 and fewer flares.

**Bot:**
- It shoots sacs (the `target()`) while they stand.
- In the drop phase it dodges the shadow: a shadow is a hostile "shot" landing at a known time. The arcs' `DODGE`
  check already handles positions and times of hostile shots, so the shadow can be fed in as one.
- It turns to aim at her while she is stunned.

## Engine work, in order

1. **Map changes for good:** `Map.dig`, `Map.fill`, `walls_version` and cache invalidation (bot wall cache, chase,
   flight, crumbs), with tests that the bot and hunters use new tunnels. Needed by 22, 23 and 25.
2. **Terrain:**
   - the `WEB` tile kind with hold and regrow (on the trail bookkeeping);
   - `RUBBLE_TILE` in `WALL_TILES`;
   - `CRACK_TILE`.
3. **Entities:**
   - `Spider`, `Crystal`, `Mole`, `Bat`, `Spiderling` (a `Hunter`), `EggSac` (a `Nest`), `GlowMushroom`;
   - the `Flare` weapon and its pickup, and `light` on projectiles for the darkness renderer.
4. **Collapse:** the `collapse` level option, the front over a distance field, `cam.shake`, and the footer status.
5. **Boss:** `BroodMotherBoss` (phases, drop with shadow, stun window, webbing tunnels).
6. **Bot:**
   - a weighted field (web and crack costs);
   - `targetable` for moles;
   - flare use;
   - the shadow as a dodge.
7. **Tools and content:**
   - `draft_garden.py cave` (and `--long`);
   - `arc4.pyxres` with five layouts;
   - the sprites above;
   - the `caves` music;
   - the map theme;
   - `campaign.yaml` arc 4.

Ouroboros stayed the finale as level 20 then; once Space and the Workshop existed too, it moved to the end of the story
(level 35), and the Caves became arc 4.

## Tests

- **Per mechanic:**
  - a web holds and regrows;
  - `dig` re-autotiles and invalidates;
  - the collapse front fills dead ends and cuts a caught tail;
  - a bat wakes in the light and flees a flare;
  - a flare burns webs;
  - the drop crushes and stuns.
- **Per level:** `bot.LEVELS` and the `WIN_RATES` bands (8 seeds), as in arc 7.
- **Registry:** new entities and tiles, no stray tiles, and `test_music` with the `caves` track.

## Open questions

- Should Collapse keep the arc's rule "one new mechanic", given it reuses webs? (Yes, as a combination, like
  Gauntlet.)
- Should moles also eat apples, so the Moles level has hunger pressure? (Probably not: one idea per level.)
- Should darkness levels show a minimap of explored tunnels? It is a nice aid, but only worth it if playtests say
  Webs or Bats feel lost.

## As built

The arc is in the game (levels 16–20, M6 in the roadmap). Where it differs from the design above, and why:

- **The neck.** Slowed by a web, the body bunches up behind the head, and the self-bite test (three segments) took
  that for a bite. `Snake.neck()` now measures the part that can't be bitten by distance along the body (3 px: still
  three segments at any normal speed); the bot's look-ahead does the same.
- **Webs.**
  - Spiders are more dangerous than designed: running into one head first is the end (as with a beetle), and one
    crawling into the body bites 4 segments off.
  - The level has a time limit (150 s at medium), and hard and nightmare spawn 2 and 4 extra crystals and more
    spiders; without that the bot won hard and nightmare nearly every time.
  - The bot needed no web costs in its way-finding: it beats the level and the bands without them.
- **Moles.**
  - Moles dig a tunnel five tiles wide (`SPADE`), not one. A one- or three-tile tunnel is a dead end the snake can't
    turn in.
  - The goal is `defeat: 8`, counting every kill (one sleeping beetle besides the moles).
  - Underground moles are not `exposed`, a new entity flag: shots and bot aims skip them.
- **Collapse.**
  - The cave-in is a goal type (`collapse: {speed, start, warn}`), like `time_limit`: always done, it is the pressure,
    and the footer shows its lead for free.
  - Its distances are octile (diagonal steps), not the four-way walking steps, which overcount bends so much that the
    front fell far behind its speed.
  - The settings are speed 30 px/s and start 4 s; the speed scales with the goals factor, and hard has its own 38.
- **Bats.**
  - The Flare is a short `Gun` whose shot becomes a `Burning` light where it comes to rest; it hurts what it hits.
  - The bot doesn't throw flares ahead: it shoots them at bats like any gun, and that is enough for the bands.
- **The Brood Mother.**
  - In her lair she hangs out of reach (shots fly underneath, she can't be touched), not armoured. Otherwise she
    stands in the line of fire of the egg sacs around her and every shot at them glances off her.
  - Dazed on the ground she can't bite, and bots don't avoid her then (otherwise they couldn't turn to shoot her).
  - No flares in the boss level: a flare pickup replaces the gun, and its four slow shots are no match for her.
  - Egg sacs are placed with open floor around them, so there is always a line of fire.
  - Bosses gained `danger()`, a circle bots keep out of: her shadow.
  - The bot stocks up on ammo while a boss offers nothing to shoot.
  - Settings: `health` 10, `drop` 5 s, `warn` 1.8 s, `stun` 5 s; one spiderling hatches per landing in the last phase.

Bot win rates (8 seeds; easy / medium / hard / nightmare):

| Level | Easy | Medium | Hard | Nightmare |
|---|---|---|---|---|
| Webs | 88% | 100% | 75% | 25% |
| Moles | 75% | 75% | 88% | 38% |
| Collapse | 100% | 100% | 38% | 25% |
| Bats | 88% | 88% | 25% | 25% |
| The Brood Mother | 75% | 75% | 38% | 12% |
