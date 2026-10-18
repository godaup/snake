"""Draft a maze around a designed pathway.

The level designer marks the intended route with path tiles on an 8-tile grid (see PATH_TILE in map.py). This script
builds a maze on that grid: cells of 7x7 floor tiles separated by 1-tile walls.

1. The path cells are put in order: the one chain that visits every path cell exactly once and ends in the cell holding
   the golden apples. The script stops if the path cannot form such a chain, and warns if it allows several.
2. The start cell is connected to the chain's first cell through cells that are not on the path.
3. Only walls between consecutive cells of start -> chain -> golden apples are opened; every other cell is attached as
   a dead-end branch (randomized Prim). The result is a perfect maze: its one and only way to the golden apples is the
   whole pathway, in order, without shortcuts.

Path tiles and entity tiles are copied over unchanged, and the floor gets a sprinkle of decorations.

The draft is written to another tilemap of the same resource file, so the source layout stays untouched:

    python tools/draft_maze.py src/snake_quest/resources/garden.pyxres --level src/snake_quest/levels/maze.yaml \\
        --src-tm 2 --dst-tm 3 --seed 7

Review the result with `snake-quest --level maze --preview maze.png` after pointing the level's `tm` at the draft.
"""

import argparse
import random
from pathlib import Path

import omegaconf
import pyxel

from snake_quest.entity import ENTITY_TILES, GoldenApple
from snake_quest.map import DECOR_TILES, EMPTY_TILE, PATH_TILE, WALL_TILE

PITCH = 8  # cell size in tiles, including one wall line
HEADER_H = 20  # world y of the map's top edge, see settings.yaml
GRASS, FLOWERS, STONE = sorted(DECOR_TILES)[:2], sorted(DECOR_TILES)[2:5], sorted(DECOR_TILES)[5]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("resources", type=Path)
    parser.add_argument("--level", type=Path, required=True, help="level YAML (for size and start position)")
    parser.add_argument("--src-tm", type=int, required=True)
    parser.add_argument("--dst-tm", type=int, required=True)
    parser.add_argument("--seed", type=int, default=7)
    return parser.parse_args()


def neighbours(cell, cols, rows):
    x, y = cell
    for nxt in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
        if 0 <= nxt[0] < cols and 0 <= nxt[1] < rows:
            yield nxt


def order_path(cells: set, goal, start_cell, cols, rows) -> list:
    """The chain through all `cells` (4-neighbouring cells in a row) that ends at `goal`. Its other end is a cell with a
    single neighbour if there is one, else the cell closest to the start."""

    def nbrs(cell):
        return [n for n in neighbours(cell, cols, rows) if n in cells]

    if start_cell in cells:
        ends = [start_cell]
    else:
        ends = [c for c in cells if c != goal and len(nbrs(c)) == 1] or sorted(
            cells - {goal}, key=lambda c: abs(c[0] - start_cell[0]) + abs(c[1] - start_cell[1])
        )
    if len(ends) > 1 and all(len(nbrs(c)) == 1 for c in ends):
        raise SystemExit(f"the path has several loose ends {sorted(ends)}; it must form one line to the golden apples")

    found: list[list] = []

    def search(chain, unvisited):
        if len(found) > 1:
            return
        here = chain[-1]
        if not unvisited:
            if here == goal:
                found.append(list(chain))
            return
        if here == goal:
            return
        # prune: every unvisited cell except the goal needs two ways in and out
        if any(c != goal and sum(n in unvisited or n == here for n in nbrs(c)) < 2 for c in unvisited):
            return
        options = sorted((n for n in nbrs(here) if n in unvisited), key=lambda n: sum(m in unvisited for m in nbrs(n)))
        for n in options:
            unvisited.discard(n)
            chain.append(n)
            search(chain, unvisited)
            chain.pop()
            unvisited.add(n)

    for end in ends:
        search([end], cells - {end})
        if found:
            break
    if not found:
        raise SystemExit(
            "the path cells cannot be walked as one line ending at the golden apples; check the path tiles"
        )
    if len(found) > 1:
        print("warning: the path can be walked in more than one order; using the first one found")
    return found[0]


def connect(frm, to, avoid: set, cols, rows) -> list:
    """Shortest cell route from `frm` to `to` that does not touch `avoid` (except `to`); [] if frm is already `to`."""
    if frm == to:
        return []
    previous = {frm: None}
    todo = [frm]
    while todo:
        cell = todo.pop(0)
        if cell == to:
            route = [cell]
            while previous[route[-1]] is not None:
                route.append(previous[route[-1]])
            return route[::-1]
        for n in neighbours(cell, cols, rows):
            if n not in previous and (n == to or n not in avoid):
                previous[n] = cell
                todo.append(n)
    raise SystemExit(f"cannot reach the start of the path {to} from the start cell {frm} without crossing the path")


def walk(edges: set, frm, to) -> list:
    """The unique cell route between two cells of a tree given by its edges."""
    links: dict = {}
    for a, b in (tuple(edge) for edge in edges):
        links.setdefault(a, []).append(b)
        links.setdefault(b, []).append(a)
    previous = {frm: None}
    todo = [frm]
    while todo:
        cell = todo.pop()
        for n in links.get(cell, []):
            if n not in previous:
                previous[n] = cell
                todo.append(n)
    route = [to]
    while previous[route[-1]] is not None:
        route.append(previous[route[-1]])
    return route[::-1]


def main() -> None:
    args = parse_args()
    resources = args.resources.resolve()  # before pyxel.init() changes the working directory
    level = omegaconf.OmegaConf.load(args.level)
    rng = random.Random(args.seed)
    pyxel.init(16, 16, headless=True)
    pyxel.load(str(resources))
    src, dst = pyxel.tilemaps[args.src_tm], pyxel.tilemaps[args.dst_tm]
    width, height = level.width // 8, level.height // 8
    cols, rows = width // PITCH, height // PITCH

    entity_sprites = set(ENTITY_TILES)
    keep = {
        (x, y): src.pget(x, y)
        for y in range(height)
        for x in range(width)
        if src.pget(x, y) == PATH_TILE or src.pget(x, y) in entity_sprites
    }
    golden_sprite = (GoldenApple._img_x, GoldenApple._img_y)
    start_cell = (int(level.start.x) // 8 // PITCH, (int(level.start.y) - HEADER_H) // 8 // PITCH)
    golden_cells = {(x // PITCH, y // PITCH) for (x, y), tile in keep.items() if tile == golden_sprite}
    if len(golden_cells) != 1:
        raise SystemExit(f"expected the golden apples in one cell, found them in {sorted(golden_cells)}")
    (goal,) = golden_cells
    path_cells = {(x // PITCH, y // PITCH) for (x, y), tile in keep.items() if tile == PATH_TILE}

    chain = order_path(path_cells | {goal}, goal, start_cell, cols, rows)
    lead_in = connect(start_cell, chain[0], avoid=path_cells | {goal}, cols=cols, rows=rows)
    solution = lead_in + chain[1:] if lead_in else chain
    tree_edges: set[frozenset] = {frozenset(pair) for pair in zip(solution, solution[1:], strict=False)}

    # attach every remaining cell as a dead-end branch (randomized Prim)
    in_maze = set(solution)
    frontier = [(cell, n) for cell in in_maze for n in neighbours(cell, cols, rows) if n not in in_maze]
    while frontier:
        cell, nxt = frontier.pop(rng.randrange(len(frontier)))
        if nxt in in_maze:
            continue
        in_maze.add(nxt)
        tree_edges.add(frozenset((cell, nxt)))
        frontier += [(nxt, n) for n in neighbours(nxt, cols, rows) if n not in in_maze]

    # draw: walls everywhere, floor inside cells, openings for tree edges
    for y in range(height):
        for x in range(width):
            dst.pset(x, y, WALL_TILE)

    def interior(cx, cy):
        xs = range(cx * PITCH + 1, min(cx * PITCH + PITCH, width - 1))
        ys = range(cy * PITCH + 1, min(cy * PITCH + PITCH, height - 1))
        return xs, ys

    for cy in range(rows):
        for cx in range(cols):
            xs, ys = interior(cx, cy)
            for y in ys:
                for x in xs:
                    dst.pset(x, y, EMPTY_TILE)
    for edge in tree_edges:
        (ax, ay), (bx, by) = sorted(edge)
        xs, ys = interior(ax, ay)
        if ay == by:  # horizontal neighbours: open the wall column between them
            for y in ys:
                dst.pset(bx * PITCH, y, EMPTY_TILE)
        else:
            for x in xs:
                dst.pset(x, by * PITCH, EMPTY_TILE)

    # a perfect maze has exactly one way between two cells: make sure it is the designed one
    assert walk(tree_edges, solution[0], solution[-1]) == solution, "the maze allows a shortcut"

    misplaced = [pos for pos in keep if dst.pget(*pos) == WALL_TILE]
    if misplaced:
        raise SystemExit(f"path or entity tiles would end up inside walls: {misplaced}")
    for (x, y), tile in keep.items():
        dst.pset(x, y, tile)

    # decorate: mostly grass, some flowers, few stones, never next to the pathway
    near_path = {(x + dx, y + dy) for (x, y) in keep for dx in (-1, 0, 1) for dy in (-1, 0, 1)}
    decorated = 0
    for y in range(height):
        for x in range(width):
            if dst.pget(x, y) != EMPTY_TILE or (x, y) in near_path:
                continue
            roll = rng.random()
            if roll < 0.03:
                tile = rng.choice(GRASS)
            elif roll < 0.038:
                tile = rng.choice(FLOWERS)
            elif roll < 0.041:
                tile = STONE
            else:
                continue
            dst.pset(x, y, tile)
            decorated += 1

    dst.imgsrc = src.imgsrc
    pyxel.save(str(resources))
    print(
        f"maze {cols}x{rows} cells; route: start {start_cell}, {max(len(lead_in) - 2, 0)} lead-in cells, "
        f"{len(chain)} path cells to the golden apples at {goal}; {len(keep)} path/entity tiles kept, "
        f"{decorated} decorations -> tilemap {args.dst_tm}"
    )


if __name__ == "__main__":
    main()
