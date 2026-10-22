# Bonus arc: The Keeper: design

Levels 36–40, unlocked after the campaign. The theme is **keeping**: the snake moves on its own, and the player is the
hand that shapes its garden. The snake is a pet now. It is played by the bot, but by a simpler bot than the one in the
tests, one whose choices can be read off the screen and predicted. The player plants hedges, apple trees, lures and
lanterns with the mouse (or a cursor on the arrow keys), and steers the snake only through what it wants. The arc
builds on what exists:
- The bot (`PathController`): its distance field, arcs, threats and the layered `bot.target` rules.
- `map.fill`/`map.dig` and `walls_version` (walls that change while playing, the bot's caches starting over).
- The hunters and `map.chase` (a shared field towards what they hunt), thorns that cut, darkness and `Entity.light`.
- The Workshop's plans (bots that follow written steps), here for the bot that plays the hand in tests.

It adds one tool per level:

| #  | Level              | New tool                                                               | Goal                         |
|----|--------------------|------------------------------------------------------------------------|------------------------------|
| 36 | Hedges             | plant and lift hedges: walls that route the snake round thorns         | length                       |
| 37 | Orchard            | plant apple trees: the only food, and where it lies steers the snake   | score, in time               |
| 38 | Lures              | wriggling lures that beetles hunt instead of the tail                  | hold a length                |
| 39 | Lanterns           | in the dark the snake sees only what is lit, and walks to the lanterns | collect all golden apples    |
| 40 | **Boss: The Crow** | a crow that steals, swoops and calls its flock; all four tools         | defeat the boss              |

The ramp:
- 36 teaches the hand on its own: the snake goes for apples, the thorns lie in its way, nothing hunts it;
- 37 makes the player decide where the snake goes (food is the leash);
- 38 adds enemies the player answers for the snake, which can't fight;
- 39 takes the snake's sight away, so the player's lights are its map;
- 40 asks for all four under pressure.

Every level fits the play area (320×192 px, 40×24 tiles): the camera stands still, and the whole garden is in reach of
the cursor. No weapons in this arc: the snake can't shoot, and its keeper can't either.

## The pet

The pet is a `PathController` with its own target rule, `keeper.pet_target`, and a few rules of its own. The bot in
the other arcs is built to win; the pet is built to be predictable. The mission screen of every level says its rules
in a line or two (see each level).

- **It eats the nearest food it can reach.** "Nearest" is by walking distance from the head (`map.flight(snake)`
  already gives distances from the head, shared and cached), not straight-line distance, so a hedge that lengthens the
  way to an apple makes another apple the nearest. Golden apples count as half as far: it prefers them.
- **It keeps its choice.** It sticks to an apple until it is eaten or gone, or until another becomes `SWITCH` (a third)
  nearer. Without that, a hedge planted near the snake would flip its choice back and forth, and the player couldn't
  plan.
- **It runs only from what it sees awake.** It keeps `THREAT` px from awake hostile entities within `SIGHT` px (64)
  of its head. It walks past sleeping ones, and so wakes them.
- **It doesn't know thorns.** Its way-finding takes thorns as floor, unlike the other bot's. This is the snake's blind
  spot, and the first reason it needs a keeper.
- **Without food it wanders.** It follows its tail round the biggest open space (`_room`), or in the dark it walks to
  the nearest lantern (level 39).
- **It never runs into a wall or into itself on its own.** The arcs, escapes and room checks stay as they are. A pet
  that crashes would make the player's work look like a coin toss.

**Its intent is drawn.** A line of faint dots from the head along its way to the target (down the distance field,
every second cell), and a small ring round the target. It is redrawn when the field is, every `FIELD_EVERY` frames,
so a planted hedge bends the line at once. A thought icon over the head says which rule is in charge: an apple
(eating), "!" (running), "…" (wandering), a light (going to a lantern). This is what lets the player predict it, and
it is the core of the arc's design: if the line is wrong, the arc doesn't work.

## The hand

**Input layer** (`keeper.Hand`, owned by the running state in Keeper levels, beside the snake's controller):
- **Mouse:** the cursor snaps to the 8 px tile under it (or the 16 px cell for trees). Left click places the current
  tool, right click lifts what the player placed there (a refund). The mouse wheel or the keys 1–4 choose the tool.
  Clicking a tool in the footer's toolbar also works.
- **Keyboard and gamepad:** the arrow keys / d-pad move the cursor a tile at a time (held: repeating). The snake
  doesn't need them here. Space / A places, X / B lifts, Tab / shoulder buttons choose the tool.
- **Cursor:** the system cursor stays hidden (`is_visible()` is False, as in other levels). The hand draws its own
  cursor in the world: the tile outlined in green where the tool can go and in red where it can't, and the tool's
  sprite beside it. So no cursor trails, and the keyboard cursor and the mouse cursor are the same thing. A mouse
  move takes the cursor over from the keys.
- **Footer:** the goals stay in the footer and shrink to the right half. The left half is the toolbar: one slot per
  tool the level gives, its sprite, how many are left, the chosen one framed.

**Rules for placing** (these keep the hand fair to the snake):
- Only on free floor (`FLOOR_TILES`): not on walls, terrain (portals, exits, thorns, ice), entities or any segment,
  and not within `CLEAR` px (24) of the head.
- **Hedges sprout.** A planted hedge is a sprout for `SPROUT` s (0.4): the pet's way-finding takes it as a wall at
  once (like `map.closing`), but it only becomes a wall (`map.fill`, autotiled) once nothing of the snake lies on it.
  A hedge can't appear under the snake or right in front of its head.
- **Budgets.** Each level gives a number of each tool (`hand: {hedge: 10, tree: 3, ...}` in the level file). Lifting
  what was placed gives it back, so the budget is a limit on what stands at once, and a hedge can be moved. Lures and
  lanterns can run out (see below). Easier difficulties give more: budgets are multiplied by the inverse of the
  `goals` factor and rounded up (`LIMIT_FIELDS`, like `time_limit`).
- **The level's own walls stay.** The hand only lifts what it planted: `map.planted` (tiles of planted hedges) and
  the hand's entities. Planted hedges are autotiled with the others and carry a small flower mark, so the player sees
  which ones can be lifted.
- `COOLDOWN` (0.15 s) between placements, so held buttons don't spray a row of hedges.

**Score.** Points come from what the snake eats, as everywhere. At level complete, every tool left unused is worth
`THRIFT` points (1), so a keeper who plants little scores more.

## Look, sound, map

- **Resources:** `keeper.pyxres` (the arc's tilemaps 0–4; images and sounds unused, as in the other arc files).
- **Layouts:** hand-drawn in the editor, or `draft_garden.py organic` for 38 and 39, with thorn beds painted by
  `thorns --region`. They are small and open, with a few long hedges that make long ways: the player's hedges must
  matter.
- **Walls:** the Garden's hedges, untinted (a return to arc 1), on a floor of evening green: `floor` colour 3 drawn
  under the decorations, and new decor (clover, a stepping stone) in row 9's free columns (12, 9) and (13, 9)
  (`DECOR_TILES` grows to 14).
- **Light:** lit, except Lanterns (39) and the boss's last phase.
- **Music:** a new `keeper` track in `tools/compose_music.py`, as sounds 40–42 (`"keeper": (40, 41, 42)` in
  `sound.MUSIC`, a track beyond the eight slots, like the Workshop's):
  - a gentle waltz in 3/4, F major, about 96 bpm;
  - a music-box lead (triangle, soft attack), a plucked bass on the first beat, brushed noise on the second and third;
  - the quietest track in the game: the player is gardening. The boss level uses `music: boss`.
- **Effects:** three new sounds on `EFFECT_CHANNEL`: `plant` (a soft rustle), `lift` (the same, rising) and `caw`
  (the crow), in `EFFECTS` and `tools/compose_effects.py`, sounds 15, 43 and 44.
- **Overview map:** a region after the story's last arc, joined to it by the road, with a little gate on the way that marks
  it as a bonus. Its theme in `campaign.yaml`: ground 3, the plain hedges, decor clover and flowers, props trees,
  lures and lanterns, boss sprite the perched crow.

### New sprites (bank 0)

Rows 25–31 are free.

| Sprite                     | Tile(s)                         | Notes                                                    |
|----------------------------|---------------------------------|----------------------------------------------------------|
| Hedge sprout, two frames   | (0, 25), (1, 25)                | drawn over the floor while it sprouts                    |
| Planted mark               | (2, 25)                         | a flower drawn over planted hedges                       |
| Sapling                    | (3, 25)                         | a tree while it grows                                    |
| Apple tree                 | (4, 25)–(5, 26)                 | 16×16 entity                                             |
| Lure, two frames           | (6, 25), (7, 25)                | a worm on a stick, wriggling                             |
| Lantern, unlit and lit     | (8, 25), (9, 25)                |                                                          |
| Thought icons              | (10, 25)–(13, 25)               | eating, running, wandering, going to a light (4×4 each, drawn small) |
| Cursor tool frames         | (14, 25), (15, 25)              | the cursor's ok / no corners                             |
| Clover, stepping stone     | (12, 9), (13, 9)                | floor decorations                                        |
| The Crow: flying, perched, stunned | (0, 27)–(5, 28)         | 16×16 each, two tiles wide; perched is the map icon      |
| Crow's shadow              | drawn by code                   | a dithered ellipse that grows                            |
| Jackdaw (the flock), two frames | (6, 27), (7, 27)           | 8×8                                                      |

## Level 36: Hedges

> Your snake eats the nearest apple. It doesn't know thorns.
> Plant hedges (left click) to lead it round them.
> Right click lifts a hedge to plant it elsewhere.

**Tool: the hedge** (see The hand, above).

**Level** (`hedges.yaml`, tm 0, 320×192):
- An open garden with three thorn beds lying on the short ways between the spots where apples come up (spawn timers
  with fixed `pos` lists: the apples come up in turn at four spots, so the player learns the pattern).
- A thorn bed cuts `HAZARD_CUT` segments a tile, as in arc 7, so a snake that crosses one shrinks. That is the cost of
  a mistake, not death: it starts 12 long, and only a snake too short dies.
- `hand: {hedge: 10}`; goal `length: 40`.
- Difficulty: speed as usual; the budget scales; hard and nightmare add a fourth thorn bed (`difficulty:` overrides)
  and apples that come up at random spots.

**The lesson:** the dotted line runs through a thorn bed, the player plants a hedge across it, and the line bends.

## Level 37: Orchard

> Nothing grows here but what you plant.
> Your snake goes for the nearest apple: plant where you want it to go.

**Tool: the apple tree.**
- Entity `Tree` (`tree`, 16×16, not hostile, `solid`: the pet keeps clear of it like a planet, and it blocks like a
  wall). Planted on a free 16 px cell, it is a sapling for `GROW` s (6), then drops an apple on a free tile within
  `DROP_REACH` (2 tiles) every `DROP` s while fewer than `CROP` (2) of its apples lie about.
- Lifting a tree gives it back but loses its apples, and a replanted tree grows again.
- The snake goes for the nearest apple, so where a tree stands decides where the snake goes, and where the player
  has to keep it safe.

**Level** (`orchard.yaml`, tm 1, 320×192):
- Two halves joined by narrow gaps, thorn beds by the gaps, and golden apples (worth the most points)
  lying deep in thorny corners, where only a well-placed tree and a few hedges get the snake in and out.
- No apples but the trees' and the golden ones.
- `hand: {tree: 3, hedge: 6}`; goals `score: 60` and `time_limit: 150`.
- Difficulty: the budget and `time_limit` scale; `DROP` scales with the `helpful` factor (`with:` per difficulty).

## Level 38: Lures

> Beetles hunt your snake's tail. Your snake can't fight.
> Lures wriggle: beetles hunt them first. Thorns kill beetles.

**Tool: the lure.**
- Entity `Lure` (`lure`, not hostile, `tally = False`). Hunters (`Hunter` and its kinds) within `LURE_RANGE` (96 px)
  hunt the nearest lure instead of the tail: `map.chase` gets a twin, `map.lure_field()`, a shared field from the
  lures, refreshed like `map.chase`.
- A hunter that reaches a lure eats at it for `FEED` s (it sits still, eyes closed: a pause, like `PAUSE`), and the
  lure is gone after `BITES` (3) such meals.
- Lures aren't refunded when eaten, only when lifted.
- **Beetles die on thorns in this arc** (`Hunter.THORN_DEATH`, as mice already do in the Workshop): a lure planted
  across a thorn bed is a trap.
- **Pens:** a hedge ring closed round a beetle counts it as defeated once it has no way to the tail and none to a lure
  (its chase field has no value at its tile). It falls asleep for good and fades out after 3 s.

**Level** (`lures.yaml`, tm 2, 320×192, `draft_garden.py organic --open` round the middle):
- Four nests round the edge that wake when the snake comes near (`Nest`, `ALERT`), apples all over, thorn beds near
  two nests.
- `hand: {lure: 4, hedge: 8}`; goal `hold_length: {length: 30, seconds: 45}`.
- Difficulty: nests spawn with the `hostile` factor; lures' `BITES` with the `helpful` factor.

## Level 39: Lanterns

> Night. Your snake sees only what is lit,
> and in the dark it walks to the nearest lantern.
> Light wakes the beetles.

**Tool: the lantern.**
- Entity `Lantern` (`lantern`, not hostile, `light` 40 px, `solid` like a small post). The level is dark
  (`darkness: {light: 20}`), and the pet's food rule only sees food in a light (its own or a lantern's:
  `darkness.lights()`, which exists).
- With nothing in sight, it walks to the nearest lantern (it wanders only when there is none). It doesn't go back to
  one it has just reached until another has been visited (`moth`: the last lantern is left out), so two lanterns make
  it go to and fro.
- **Sleepers wake in light**, like bats: a beetle that a lantern's light falls on wakes. A lantern near a nest is a
  mistake, or bait with a lure.
- Lanterns burn for `OIL` s (40) and go out; lifting one before then gives it back with the oil it has left.

**Level** (`lanterns.yaml`, tm 3, 320×192):
- Five golden apples in the dark (lit by nothing), sleeping beetles on the ways between them, a few apples.
- `hand: {lantern: 4, hedge: 6, lure: 2}`; goal `collect_all: golden`.
- Difficulty: `OIL` scales with the `helpful` factor; the darkness with `light`; hard and nightmare add a
  `time_limit`.

## Level 40: Boss: The Crow

> The Crow has come for your garden.
> It lands to feed, swoops at the tail and calls its flock.
> Only while it is down can your snake bite it.

**Boss** `CrowBoss` (`crow`). A 16×16 `Crow` entity flies over the garden: over the walls, not touchable while
flying, a shadow under it. The snake can't shoot. It hurts the Crow only by running its head into it while the Crow is
on the ground, so the player's work is getting the Crow down where the snake will go. Each bite costs it one of its
`health` (6 at medium) and sends it up again. Three phases, by `below`:

1. **The thief (above 2/3).**
   - Every `steal` s, it flies to the tree with the most apples and perches there, eating one apple every second for
     `perch` s.
   - The snake bites it if it comes to that tree in time. The pet goes for the nearest apple, and the Crow sits on a
     tree's apples, so the bite comes from planting trees where the snake is going and hedging its way there.
   - No tree with apples: it pulls up a planted hedge instead (grounded for `pull` s, a chance for a bite too).
2. **The swoop (above 1/3).**
   - Every `swoop` s it dives at the snake's tail, from its place in the sky along a straight line. Its shadow runs
     along that line for `warn` s first.
   - A hit cuts `CHUNK` segments off the tail.
   - A hedge standing on the line when it dives stops it: it crashes, lies stunned for `stun` s, and the pet takes the
     stunned Crow as its target (the boss's `target()`, ahead of food). So the answer is a hedge planted across the
     shadow in time.
   - The phase message is "THE CROW STOOPS".
3. **The flock (below 1/3).**
   - Dusk falls: the light shrinks from `light[0]` to `light[1]` over the phase, so the lanterns come into play.
   - It calls jackdaws (`call` s, up to `flock`): `Jackdaw`, an 8×8 flying hunter that pecks the tail
     (`CHUNK`) and goes for lures first, like beetles.
   - It goes on swooping, faster.
   - The phase message is "THE SKY GOES BLACK".

**Boss settings:**
- `pressure`: `health`, `swoop` (divided: more often), `flock`;
- `relief`: `perch`, `stun`, `warn`;
- `bar()`: its health;
- `target()`: the Crow while it is on the ground and within `REACH` (160 px of walking) of the head, else `None`;
- `danger()`: the swoop line while it warns (circles along it), so the pet runs from it as a player would want, and
  the line is drawn for the player too.

**Level** (`crow.yaml`, tm 4, 320×192):
- An open garden, few walls, thorn beds at the edges.
- `hand: {hedge: 10, tree: 3, lure: 3, lantern: 3}`; goal `boss: defeated`, `music: boss`.

## The bot that plays the hand

Every level must be winnable, and a test plays it through (the roadmap's rule). Here the snake is already a bot; the
test needs a second one for the player's hand. It is `keeper.HandBot`, which places tools through the same input
methods as `Hand` (`place(tool, tile)`, `lift(tile)`), so it can't do what the player can't.
- **Human limits:** it acts at most once every `REACTION` s (0.35), and its cursor moves at most `CURSOR_SPEED` tiles
  a second. A bot that plants a hedge in the frame the shadow appears would make the win rates meaningless.
- **A plan for what stays:** the level file's `keeper:` section lists placements, for bots only (like the
  Workshop's `plan`):

  ```yaml
  keeper:
    - hedge: [[12, 7], [12, 8], [12, 9]]   # at the start
    - tree: [[30, 4]]
    - after: {length: 25}                   # wait until
    - lift: [[12, 8]]
    - lantern: [[5, 20], [18, 14], [33, 6]] # placed in turn, each once the pet has reached the one before
  ```

- **Rules for what can't be planned:**
  - lures: a hunter within `LURE_AT` px (48) of the tail gets a lure on a free tile between it and the
    nearest thorn bed (or `LURE_OFF` px away from the snake);
  - swoops: a hedge on the swoop line, at its middle, while the shadow warns;
  - the thief: a tree on free floor about `AHEAD` px along the pet's intent line.
- **The proof that the hand matters:** `tests/test_winnable.py` plays each Keeper level twice, with the hand bot (it
  must win within the `WIN_RATES` band) and with no hand at all (it must lose at least `HELPLESS` = 75% of seeds).
  That checks the levels' design as well as the engine: a level the snake wins alone teaches nothing.

## Engine work, in order

1. **Arc and unlocking:**
   - `campaign.yaml` arc 8 with `bonus: true`; `Campaign.story_last` (the last level not in a bonus arc).
   - `game.level_up()` shows `VICTORY` after the story's last level as now, and opens the Keeper's region on the map
     (`unlocked_arcs()` already opens it once the story's last arc is done).
   - After level 40 it returns to the level select with a short "THE GARDEN IS KEPT" panel (a `VictoryStateHandler`
     variant).
2. **The pet:**
   - `keeper.pet_target`: walking distance, `SWITCH`, golden preference, sight in the dark, lanterns, `SIGHT`;
   - `PathController(thorns=False)` (its way-finding sees thorns as floor);
   - the intent line and thought icon (`PetController.intent()`, drawn by the running state over the map).
3. **The hand:** `keeper.Hand` (mouse, keys, gamepad; cursor; budgets; placing rules); `map.planted`, sprouts (`map.fill`
   once clear, `walls_version`); the toolbar in `Hud`; `RunningStateHandler` builds a `Hand` when the level has
   `hand:`.
4. **Tools:** `Tree`, `Lure` and `map.lure_field()`, `Lantern` (oil, `moth`, waking sleepers), `Hunter.THORN_DEATH`
   and pens.
5. **Boss:** `CrowBoss`, `Crow`, `Jackdaw`; the swoop line in `danger()`.
6. **Bot for tests:** `keeper.HandBot` and the `keeper:` plan; `bot.LEVELS`, `WIN_RATES`, the no-hand check.
7. **Content:** `keeper.pyxres`, the sprites, the `keeper` music and the effects, the map theme, the five level files.

## Tests

- **The pet:**
  - it picks the nearest apple by walking distance, not straight-line distance;
  - it keeps its choice until another is `SWITCH` nearer;
  - it walks through thorns and past a sleeping beetle, and runs from an awake one within `SIGHT`;
  - in the dark it ignores unlit food and walks to a lantern;
  - the intent line ends at its target and changes when a hedge is planted across it.
- **The hand:**
  - placing is refused on walls, terrain, entities, segments and near the head;
  - a hedge sprouts and becomes a wall only once the snake has left it; the budget goes down and lifting gives it
    back;
  - the level's own walls can't be lifted;
  - mouse, keys and gamepad reach the same `place`/`lift`;
  - no cursor trail (the hand's cursor is drawn by the running state, which repaints every frame).
- **Tools:** a tree grows and drops at most `CROP` apples; a hunter hunts a lure in range and eats it in `BITES`
  meals; a beetle on thorns dies; a penned beetle counts as defeated; a lantern wakes a sleeper, runs out of oil, and
  refunds what is left.
- **The Crow:** it is bitten only on the ground; a hedge on the swoop line stuns it; the phases by `below`.
- **Per level:** the hand bot wins within the band, and no hand loses (`HELPLESS`).
- **Registry:** the new entities and decor, `test_music` with the `keeper` track, the new effects.

## Open questions

- **Is the pet blind to thorns?** It gives level 36 its job, and the lesson is clear. The alternative, a pet that
  sees thorns but cuts corners near them, is more natural but harder to read. Recommendation: blind, and the mission
  says so.
- **Pausing to plan.** Holding Shift could slow the game to half speed while the hand works (a "keeper's breath").
  It would make the boss's swoops easier to answer for people who aren't fast with a mouse. Recommendation: try it in
  playtests before adding it; the budget, not speed, should be the hard part.
- **Budgets vs. cooldowns.** Budgets with refunds make the hand a puzzle (where to put ten hedges); cooldowns
  alone would make it a reflex game. Recommendation: budgets.
- **Scrolling levels.** All five fit the screen, which keeps the cursor simple. A bigger garden would need the
  camera to follow the cursor while it is near an edge, not the head. Leave that until a level needs it.
- **The one-off levels.** Shepherd (the body herds critters into a pen) fits this arc's spirit but asks the player to
  steer. It stays a one-off for the campaign; a Keeper version (the player builds the fences, the snake drives the
  flock) could be a sixth level later.

## As built

The arc is in the game (levels 36–40, M9 in the roadmap). Its balancing is not finished: this section records where
it stands.

### Balancing: open issues

Bot win rates with the `HandBot` (8 seeds, `tools/balance.py --levels hedges orchard lures lanterns crow --seeds 8`;
easy / medium / hard / nightmare). The bands are those of `tests/test_winnable.py` (`WIN_RATES`: easy 75–100%,
medium 50–100%, hard 25–90%, nightmare 10–70%; a harder difficulty must not be won more often, give or take one
seed). Out of band in bold.

| Level | Easy | Medium | Hard | Nightmare | Losses (hard, nightmare) |
|---|---|---|---|---|---|
| Hedges | 100% | 75% | **0%** | **0%** | killed 8, killed 8 |
| Orchard | 75% | 75% | 50% | 38% | tail 3, killed 1; tail 3, killed 2 |
| Lures | 100% | 75% | **12%** | **0%** | killed 3, tail 2, wall 2; killed 7, wall 1 |
| Lanterns | **62%** | 100% | **12%** | **25%** | killed 4, wall 3; wall 3, tail 2, killed 1 |
| Boss: The Crow | 88% | 62% | 38% | **0%** | tail 5; tail 8 |

Orchard was measured with its difficulty overrides; the others before the budget fix below. So
`test_difficulties_keep_their_win_rates` (slow) fails for Hedges, Lures, Lanterns and the Crow.

- **Tool budgets (fixed, not yet re-measured).** The hand divided its budgets by the goals factor itself, after the
  level's per-difficulty overrides were merged, so an override was scaled again. On hard Hedges had 10 hedges and
  its plan needs 12 for the four thorny gaps; the pet walked into the open ones ("killed 8" on hard and nightmare).
  Lures needs 16 for the two pens and had 14 and 12. The budgets now scale in `difficulty.apply` with everything
  else, and Hedges (`hedge: 12`) and Lures (`hedge: 16`) override them on hard and nightmare. Next: re-measure both.
  If Hedges on hard is then won about as often as on medium, harder could mean a faster apple turn-over instead.
- **Orchard (in band).** The score goal scaled to 48 and 56 grew the snake (3 segments an apple) past 140, and it
  bit itself. Hard and nightmare keep a score of 40: harder means less time and a faster snake.
- **Lanterns (not investigated).** Easy loses to beetles (killed 2) and hard to beetles and walls; nightmare beats
  hard by more than the one-seed slack. Easy's brighter light (`light` 1.3) may wake the sleeping beetles sooner, and
  its slower snake gives them longer to catch it; hard's dimmer light (0.9) may leave the pet blind between lanterns
  for longer. To look at: the outcomes per seed (who kills it, and where), then light or beetle overrides per
  difficulty.
- **Boss: The Crow, nightmare.** Every loss is the pet biting itself at 69–106 segments, with the Crow on 1–4 of its
  7 health (6 scaled by the `boss` factor 1.2): the longer fight lets the trees and apples grow the snake too long.
  To try: `nightmare: {boss: {health: 6}}`, or fewer apples (the `apples` timer's `max: 1`), or a larger `chunk` so
  the swoops keep it short.
- **The pet alone (`test_the_garden_needs_its_keeper`, slow).** It last failed for Lures (the pet won 3 of 4 runs
  alone). Two beetles a nest (`BROOD: 2`, `SPAWN: 12`) brought that to 0 of 8 at medium (`--no-hand`), but the slow
  test hasn't been rerun since.
