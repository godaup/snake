"""Level layout helpers: decorate a level's floor, or generate a natural ("organic"), a fortress or a temple layout.

    # sprinkle grass, flowers and stones on a level's empty floor (in place)
    python tools/draft_garden.py decorate src/snake_quest/resources/garden.pyxres \\
        --level src/snake_quest/levels/classic.yaml --seed 1

    # generate a natural layout into a free tilemap, keeping the level's entity, portal, exit and hazard tiles
    python tools/draft_garden.py organic src/snake_quest/resources/garden.pyxres \\
        --level src/snake_quest/levels/maneuver.yaml --src-tm 1 --dst-tm 4 --seed 3

    # paint patches of ice on a level's floor (in place)
    python tools/draft_garden.py ice src/snake_quest/resources/arc3.pyxres \\
        --level src/snake_quest/levels/ice.yaml --patches 14 --seed 3

    # the same with straight walls and towers (arc 3; levels there tint the hedges into stone)
    python tools/draft_garden.py fortress src/snake_quest/resources/arc3.pyxres \\
        --level src/snake_quest/levels/turrets.yaml --src-tm 0 --dst-tm 0 --seed 1

    # the same with pillars and short walls (arc 4, the temple), and patches of mirrored floor
    python tools/draft_garden.py temple src/snake_quest/resources/arc4.pyxres \\
        --level src/snake_quest/levels/trail.yaml --src-tm 0 --dst-tm 0 --seed 1
    python tools/draft_garden.py mirror src/snake_quest/resources/arc4.pyxres \\
        --level src/snake_quest/levels/mirror.yaml --bands 3 --seed 1

    # small clusters of thorns, here only between tile columns 100 and 150 (--region works for ice and mirror too)
    python tools/draft_garden.py thorns src/snake_quest/resources/arc4.pyxres \\
        --level src/snake_quest/levels/gauntlet.yaml --patches 20 --region 100 150 --seed 1

The organic layout is a hedge border plus rounded bushes (unions of circles) and gently curved hedge rows. Every
obstacle keeps CLEARANCE tiles of open floor to the next one, the area around the start stays clear, and floor the snake
cannot reach is filled in, so nothing spawns in a closed pocket. Review with `snake-quest --level NAME --preview x.png`.
"""

import argparse
import math
import random
from collections import deque
from pathlib import Path

import omegaconf
import pyxel

from snake_quest.entity import ENTITY_TILES
from snake_quest.tiles import (
    DECOR_TILES,
    EMPTY_TILE,
    EXIT_TILE,
    HAZARD_TILE,
    ICE_TILE,
    MIRROR_TILE,
    PORTAL_TILES,
    WALL_TILE,
)

HEADER_H = 20  # world y of the map's top edge, see settings.yaml
CLEARANCE = 3  # tiles of open floor between obstacles (the snake needs room to turn, also when boosted)
START_CLEAR = 6  # tiles around the start kept free of obstacles and decorations
GRASS, FLOWERS, STONE = sorted(DECOR_TILES)[:2], sorted(DECOR_TILES)[2:5], sorted(DECOR_TILES)[5]
FLOOR = DECOR_TILES | {EMPTY_TILE}


def start_tile(level) -> tuple[int, int]:
    return int(level.start.x) // 8, (int(level.start.y) - HEADER_H) // 8


def decorate(tilemap, width, height, rng, avoid: set, density: float = 1.0) -> int:
    """Put decorations on empty floor tiles that are not in `avoid`; returns how many."""
    count = 0
    for y in range(height):
        for x in range(width):
            if tilemap.pget(x, y) != EMPTY_TILE or (x, y) in avoid:
                continue
            roll = rng.random() / density
            if roll < 0.03:
                tile = rng.choice(GRASS)
            elif roll < 0.038:
                tile = rng.choice(FLOWERS)
            elif roll < 0.041:
                tile = STONE
            else:
                continue
            tilemap.pset(x, y, tile)
            count += 1
    return count


def ice(tilemap, width, height, rng, avoid: set, patches: int, tile=ICE_TILE, region=None, sizes=(2.5, 6.0)) -> int:
    """Paint `patches` rounded patches of ice (or another floor `tile`) on floor tiles that are not in `avoid`, between
    the tile columns of `region` if given; returns how many tiles."""
    x0, x1 = region or (3, width - 4)
    count = 0
    for _ in range(patches):
        patch = bush(rng, rng.uniform(x0, x1), rng.uniform(3, height - 4), rng.uniform(*sizes))
        for x, y in patch:
            if 0 <= x < width and 0 <= y < height and (x, y) not in avoid and tilemap.pget(x, y) in FLOOR:
                tilemap.pset(x, y, tile)
                count += 1
    return count


def bands(tilemap, width, height, rng, avoid: set, count: int, tile, region=None) -> int:
    """Paint `count` wavy bands of `tile` from the top wall to the bottom one, evenly spread over the width, so every
    way from left to right crosses them; returns how many tiles."""
    painted = 0
    x0, x1 = region or (0, width)
    for index in range(count):
        center = x0 + (x1 - x0) * (index + 1) / (count + 1)
        phase, thickness = rng.uniform(0, math.tau), rng.randint(5, 7)
        for y in range(1, height - 1):
            x0 = round(center + 3 * math.sin(y / 4 + phase) - thickness / 2)
            for x in range(x0, x0 + thickness):
                if (x, y) not in avoid and tilemap.pget(x, y) in FLOOR:
                    tilemap.pset(x, y, tile)
                    painted += 1
    return painted


def near(points, radius: int) -> set:
    return {
        (x + dx, y + dy) for x, y in points for dx in range(-radius, radius + 1) for dy in range(-radius, radius + 1)
    }


def bush(rng, cx, cy, size) -> set:
    """A rounded bush: a few overlapping circles around a centre."""
    tiles = set()
    for _ in range(rng.randint(2, 4)):
        ox, oy = rng.uniform(-size / 2, size / 2), rng.uniform(-size / 2, size / 2)
        r = rng.uniform(size * 0.45, size * 0.75)
        for y in range(int(cy + oy - r) - 1, int(cy + oy + r) + 2):
            for x in range(int(cx + ox - r) - 1, int(cx + ox + r) + 2):
                if (x - cx - ox) ** 2 + (y - cy - oy) ** 2 <= r * r:
                    tiles.add((x, y))
    return tiles


def smooth(shape: set, rounds: int = 2) -> set:
    """Round off a blocky shape: each tile becomes wall if most of its 3x3 neighbourhood is wall."""
    for _ in range(rounds):
        candidates = near(shape, 1)
        shape = {
            (x, y)
            for x, y in candidates
            if sum((x + dx, y + dy) in shape for dx in (-1, 0, 1) for dy in (-1, 0, 1)) >= 5
        }
    return shape


def flower_bed(rng, cx, cy) -> dict:
    """A small dense patch of flowers with some grass."""
    bed = {}
    r = rng.uniform(1.2, 2.2)
    for y in range(int(cy - r) - 1, int(cy + r) + 2):
        for x in range(int(cx - r) - 1, int(cx + r) + 2):
            if (x - cx) ** 2 + (y - cy) ** 2 <= r * r and rng.random() < 0.7:
                bed[x, y] = rng.choice(FLOWERS) if rng.random() < 0.7 else rng.choice(GRASS)
    return bed


def hedge_row(rng, x0, y0, length, angle, thickness) -> set:
    """A gently curving hedge row: a line whose direction drifts along a sine."""
    tiles = set()
    x, y = float(x0), float(y0)
    wobble, phase = rng.uniform(0.25, 0.5), rng.uniform(0, math.tau)
    for step in range(length * 2):
        heading = angle + wobble * math.sin(step / 6 + phase)
        x += math.cos(heading) * 0.5
        y += math.sin(heading) * 0.5
        for dx in range(thickness):
            for dy in range(thickness):
                tiles.add((round(x) + dx, round(y) + dy))
    return tiles


def garden_shape(rng, width, height) -> set:
    """A rounded bush or a curved hedge row."""
    if rng.random() < 0.3:
        shape = hedge_row(
            rng,
            rng.uniform(4, width - 5),
            rng.uniform(4, height - 5),
            rng.randint(10, 20),
            rng.uniform(0, math.tau),
            2,
        )
    else:
        shape = bush(rng, rng.uniform(5, width - 6), rng.uniform(5, height - 6), rng.uniform(2.5, 5.0))
    return smooth(shape)


def fortress_shape(rng, width, height) -> set:
    """A tower (a block) or a straight wall, two tiles thick, which may turn a corner."""
    x0, y0 = rng.randint(4, width - 6), rng.randint(4, height - 6)
    if rng.random() < 0.35:
        w, h = rng.randint(2, 5), rng.randint(2, 5)
        return {(x0 + dx, y0 + dy) for dx in range(w) for dy in range(h)}
    length, horizontal = rng.randint(6, 16), rng.random() < 0.5
    tiles = {(x0 + i, y0 + t) if horizontal else (x0 + t, y0 + i) for i in range(length) for t in range(2)}
    if rng.random() < 0.5:  # an L: a second wall from one end
        end, turn, sign = rng.choice([0, length - 2]), rng.randint(4, 10), rng.choice([-1, 1])
        for i in range(turn):
            for t in range(2):
                tiles.add((x0 + end + t, y0 + sign * i) if horizontal else (x0 + sign * i, y0 + end + t))
    return tiles


def temple_shape(rng, width, height) -> set:
    """A pillar (2x2) or a short wall, one tile thick."""
    x0, y0 = rng.randint(4, width - 6), rng.randint(4, height - 6)
    if rng.random() < 0.6:
        return {(x0 + dx, y0 + dy) for dx in range(2) for dy in range(2)}
    length, horizontal = rng.randint(3, 7), rng.random() < 0.5
    return {(x0 + i, y0) if horizontal else (x0, y0 + i) for i in range(length)}


def organic(
    tilemap, width, height, rng, start, keep: dict, shape_of=garden_shape, beds=True, open_areas=()
) -> tuple[int, int]:
    walls = {(x, y) for y in range(height) for x in range(width) if x in (0, width - 1) or y in (0, height - 1)}
    # kept free of obstacles: around the start and the open areas (x, y, radius in tiles, e.g. a boss arena)
    blocked_start = near([start], START_CLEAR) | {
        (x, y)
        for cx, cy, r in open_areas
        for x in range(cx - r, cx + r + 1)
        for y in range(cy - r, cy + r + 1)
        if (x - cx) ** 2 + (y - cy) ** 2 <= r * r
    }
    placed = 0
    attempts = 0
    while attempts < 400:
        attempts += 1
        shape = shape_of(rng, width, height)
        if not shape:
            continue
        inside = all(CLEARANCE <= x < width - CLEARANCE and CLEARANCE <= y < height - CLEARANCE for x, y in shape)
        if not inside or shape & blocked_start or near(shape, CLEARANCE) & walls or near(shape, 1) & set(keep):
            continue
        walls |= shape
        placed += 1
    for y in range(height):
        for x in range(width):
            tilemap.pset(x, y, WALL_TILE if (x, y) in walls else EMPTY_TILE)
    # fill floor the snake cannot reach from the start
    reachable, queue = {start}, deque([start])
    while queue:
        x, y = queue.popleft()
        for nxt in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
            if 0 <= nxt[0] < width and 0 <= nxt[1] < height and nxt not in reachable and nxt not in walls:
                reachable.add(nxt)
                queue.append(nxt)
    filled = 0
    for y in range(height):
        for x in range(width):
            if (x, y) not in walls and (x, y) not in reachable:
                tilemap.pset(x, y, WALL_TILE)
                filled += 1
    for (x, y), tile in keep.items():
        tilemap.pset(x, y, tile)
    # a few flower beds in open spots
    count = 0
    for _ in range(60 if beds else 0):
        if count >= max(3, width * height // 700):
            break
        cx, cy = rng.uniform(4, width - 5), rng.uniform(4, height - 5)
        bed = flower_bed(rng, cx, cy)
        if near(bed, 2) & (walls | set(keep)) or set(bed) & blocked_start:
            continue
        for (x, y), tile in bed.items():
            tilemap.pset(x, y, tile)
        count += 1
    return placed, filled


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("command", choices=["decorate", "organic", "fortress", "temple", "ice", "mirror", "thorns"])
    parser.add_argument("resources", type=Path)
    parser.add_argument("--level", type=Path, required=True)
    parser.add_argument("--src-tm", type=int, help="organic: tilemap whose entity tiles are kept")
    parser.add_argument("--dst-tm", type=int, help="organic: tilemap to write (decorate uses the level's tm)")
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--patches", type=int, default=12, help="ice/mirror: how many patches")
    parser.add_argument("--bands", type=int, default=0, help="mirror: bands across the level instead of patches")
    parser.add_argument(
        "--region", type=int, nargs=2, metavar=("X0", "X1"), help="ice/mirror/thorns: only between these tile columns"
    )
    parser.add_argument(
        "--open",
        type=int,
        nargs=3,
        action="append",
        default=[],
        metavar=("X", "Y", "R"),
        help="organic/fortress: keep a circle of R tiles around tile (X, Y) free, e.g. a boss arena (repeatable)",
    )
    args = parser.parse_args()
    resources = args.resources.resolve()  # before pyxel.init() changes the working directory
    level = omegaconf.OmegaConf.load(args.level)
    rng = random.Random(args.seed)
    pyxel.init(16, 16, headless=True)
    pyxel.load(str(resources))
    width, height = level.width // 8, level.height // 8
    start = start_tile(level)
    # entities and special terrain survive a new layout
    entity_sprites = set(ENTITY_TILES) | set(PORTAL_TILES) | {EXIT_TILE, HAZARD_TILE, ICE_TILE, MIRROR_TILE}

    if args.command in ("ice", "mirror", "thorns"):
        tilemap = pyxel.tilemaps[level.tm]
        kept = [(x, y) for y in range(height) for x in range(width) if tilemap.pget(x, y) in entity_sprites]
        tile = {"ice": ICE_TILE, "mirror": MIRROR_TILE, "thorns": HAZARD_TILE}[args.command]
        avoid = near([start], START_CLEAR) | near(kept, 3)
        if args.bands:
            count = bands(tilemap, width, height, rng, avoid, args.bands, tile, args.region)
        elif args.command == "thorns":  # small clusters, with room to steer between them
            count = ice(tilemap, width, height, rng, avoid, args.patches, tile, args.region, sizes=(0.8, 1.6))
        else:
            count = ice(tilemap, width, height, rng, avoid, args.patches, tile, args.region)
        print(f"tilemap {level.tm}: {count} {args.command} tiles")
    elif args.command == "decorate":
        tilemap = pyxel.tilemaps[level.tm]
        entities = [(x, y) for y in range(height) for x in range(width) if tilemap.pget(x, y) in entity_sprites]
        count = decorate(tilemap, width, height, rng, avoid=near([start], START_CLEAR) | near(entities, 1))
        print(f"tilemap {level.tm}: {count} decorations")
    else:
        src, dst = pyxel.tilemaps[args.src_tm], pyxel.tilemaps[args.dst_tm]
        keep = {(x, y): src.pget(x, y) for y in range(height) for x in range(width) if src.pget(x, y) in entity_sprites}
        if args.command in ("fortress", "temple"):  # sparse rubble instead of flower beds
            shape_of = fortress_shape if args.command == "fortress" else temple_shape
            placed, filled = organic(
                dst, width, height, rng, start, keep, shape_of=shape_of, beds=False, open_areas=args.open
            )
            density = 0.4
        else:
            placed, filled = organic(dst, width, height, rng, start, keep, open_areas=args.open)
            density = 1.0
        count = decorate(dst, width, height, rng, avoid=near([start], START_CLEAR) | near(keep, 1), density=density)
        dst.imgsrc = src.imgsrc
        print(f"tilemap {args.dst_tm}: {placed} obstacles, {filled} unreachable tiles filled, {count} decorations")
    pyxel.save(str(resources))


if __name__ == "__main__":
    main()
