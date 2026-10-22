"""Check and solve Workshop puzzles (arc 5) on their text (tools/puzzles/*.txt, see draft_workshop.py).

    python tools/solve_workshop.py check tools/puzzles/crates.txt src/snake_quest/levels/crates.yaml
    python tools/solve_workshop.py solve tools/puzzles/crates.txt

`check` plays a level's `plan` on the puzzle: every push must start from a cell the snake can reach behind the crate
and move it over free cells, and at the end the exit must be in reach. `solve` searches for the fewest pushes that
open the way to the exit (breadth first over the crates' cells; the snake is a point that can't pass crates or shut
gates) and prints them as plan steps. Both treat the snake as small: whether it can turn in a lane, and plates held by
its body, are left to the bot (tests/test_winnable.py).
"""

import argparse
import sys
from collections import deque
from pathlib import Path

DIRECTIONS = {"right": (1, 0), "down": (0, 1), "left": (-1, 0), "up": (0, -1)}
BELTS = {">": (1, 0), "v": (0, 1), "<": (-1, 0), "^": (0, -1)}
ON_BELT = {")": ">", "V": "v", "(": "<", "A": "^"}  # a crate on a belt
GATES = {"R": "r", "B": "b", "Y": "y"}
SOLID = set("#123")  # walls and locks


class Puzzle:
    def __init__(self, lines: list[str]):
        width = max(len(line) for line in lines)
        self.cells = {(x, y): (line[x] if x < len(line) else "#") for y, line in enumerate(lines) for x in range(width)}
        self.crates = frozenset(cell for cell, ch in self.cells.items() if ch == "$" or ch in ON_BELT)
        self.cells = {cell: ON_BELT.get(ch, ch) for cell, ch in self.cells.items()}
        self.start = next(cell for cell, ch in self.cells.items() if ch == "@")
        self.exits = {cell for cell, ch in self.cells.items() if ch == "E"}
        self.plates = {colour: {c for c, ch in self.cells.items() if ch == colour} for colour in GATES.values()}

        self.belts = {cell: BELTS[ch] for cell, ch in self.cells.items() if ch in BELTS}
        self.held: set = set()  # plate cells the body holds (check: the plan's visits)
        self.unlocked: set = set()  # lock cells opened (check: the plan's unlocks)

    def open(self, crates: frozenset) -> set[str]:
        """The gates (letters) whose plates all bear crates (or the body)."""
        return {
            gate for gate, plate in GATES.items() if self.plates[plate] and self.plates[plate] <= crates | self.held
        }

    def blocked(self, cell, crates: frozenset, opened: set[str]) -> bool:
        ch = self.cells.get(cell, "#")
        if cell in self.unlocked:
            return cell in crates
        return ch in SOLID or (ch in GATES and ch not in opened) or cell in crates

    def reach(self, start, crates: frozenset) -> set:
        """The cells the snake can get to from `start`."""
        opened = self.open(crates)
        seen, queue = {start}, deque([start])
        while queue:
            x, y = queue.popleft()
            for dx, dy in DIRECTIONS.values():
                nxt = (x + dx, y + dy)
                if nxt not in seen and not self.blocked(nxt, crates, opened):
                    seen.add(nxt)
                    queue.append(nxt)
        return seen

    def ride(self, crates: frozenset) -> frozenset:
        """Crates carried along their belts until each is stopped (or has left the belt)."""
        moved = True
        while moved:
            moved = False
            for crate in sorted(crates):
                d = self.belts.get(crate)
                ahead = d and (crate[0] + d[0], crate[1] + d[1])
                if d and not self.blocked(ahead, crates, self.open(crates)):
                    crates, moved = crates - {crate} | {ahead}, True
        return crates

    def flip(self, cell) -> None:
        """A lever thrown: the belts of its room run the other way."""
        numbers = rooms(self)
        for belt, (dx, dy) in list(self.belts.items()):
            if numbers.get(belt) == numbers.get(cell):
                self.belts[belt] = (-dx, -dy)

    def push(self, crates: frozenset, region: set, crate, d) -> frozenset | None:
        """The crates after pushing `crate` one cell along `d`, or None when that isn't possible from `region`."""
        behind, ahead = (crate[0] - d[0], crate[1] - d[1]), (crate[0] + d[0], crate[1] + d[1])
        if crate not in crates or behind not in region or self.blocked(ahead, crates, self.open(crates)):
            return None
        return crates - {crate} | {ahead}


def read(path: Path) -> list[str]:
    lines = [line.rstrip("\n") for line in path.read_text().splitlines() if not line.startswith(";")]
    while lines and not lines[-1].strip():
        lines.pop()
    return lines


def check(puzzle: Puzzle, plan) -> list[str]:
    """Problems with a plan (empty when it works)."""
    crates, snake, problems = puzzle.crates, puzzle.start, []
    for room in plan:
        for step in room["steps"]:
            kind, value = next(iter(step.items())) if isinstance(step, dict) else (step, None)
            crates = puzzle.ride(crates)
            if kind == "lever":
                puzzle.flip(tuple(value))
                crates = puzzle.ride(crates)
                continue
            if kind in ("visit", "unlock"):  # the body on a plate (held while the head goes on), a key in its lock
                target = tuple(value)
                region = puzzle.reach(snake, crates)
                if target not in region and not _beside(region, target):
                    problems.append(f"can't get to {list(target)}")
                    return problems
                if kind == "unlock":
                    puzzle.unlocked |= _lock(puzzle, target)
                elif puzzle.cells.get(target) in GATES.values():
                    puzzle.held.add(target)
                if puzzle.cells.get(target) not in SOLID:
                    snake = target
                continue
            if kind != "push":
                continue
            cell, direction, cells = tuple(value[0]), value[1], value[2]
            d = DIRECTIONS[direction]
            for _ in range(cells):
                after = puzzle.push(crates, puzzle.reach(snake, crates), cell, d)
                if after is None:
                    problems.append(f"can't push the crate on {list(cell)} {direction}")
                    return problems
                crates, snake, cell = after, cell, (cell[0] + d[0], cell[1] + d[1])
    crates = puzzle.ride(crates)
    if not puzzle.exits & puzzle.reach(snake, crates):
        problems.append("the exit is out of reach at the end")
    return problems


def rooms(puzzle: Puzzle) -> dict:
    """Room number per cell: the areas between gates (gates and walls count as walls)."""
    numbers: dict = {}
    for cell, ch in puzzle.cells.items():
        if cell in numbers or ch in SOLID or ch in GATES:
            continue
        number, queue = len(set(numbers.values())), deque([cell])
        numbers[cell] = number
        while queue:
            x, y = queue.popleft()
            for dx, dy in DIRECTIONS.values():
                nxt = (x + dx, y + dy)
                ch = puzzle.cells.get(nxt, "#")
                if nxt not in numbers and ch not in SOLID and ch not in GATES:
                    numbers[nxt] = number
                    queue.append(nxt)
    return numbers


def dead(puzzle: Puzzle, cell) -> bool:
    """A crate in a corner (walls on two sides that meet) can never move again: dead unless it is on a plate."""
    if puzzle.cells.get(cell) in GATES.values():
        return False

    def wall(dx, dy):
        return puzzle.cells.get((cell[0] + dx, cell[1] + dy), "#") in SOLID

    return (wall(1, 0) or wall(-1, 0)) and (wall(0, 1) or wall(0, -1))


def _beside(region: set, cell) -> bool:
    return any((cell[0] + dx, cell[1] + dy) in region for dx, dy in DIRECTIONS.values())


def _lock(puzzle: Puzzle, cell) -> set:
    """The cells of the lock at `cell` (all of its colour that touch)."""
    ch, group, queue = puzzle.cells[cell], {cell}, deque([cell])
    while queue:
        x, y = queue.popleft()
        for dx, dy in DIRECTIONS.values():
            nxt = (x + dx, y + dy)
            if nxt not in group and puzzle.cells.get(nxt) == ch:
                group.add(nxt)
                queue.append(nxt)
    return group


def solve(puzzle: Puzzle, limit: int = 300_000) -> list[tuple] | None:
    """The fewest pushes (crate cell, direction), room by room, that bring the exit in reach, or None. Each stage
    pushes only the crates in the snake's room and ends once another room (or the exit) is in reach."""
    numbers = rooms(puzzle)
    crates, snake, moves, done = puzzle.crates, puzzle.start, [], set()
    while True:
        region = puzzle.reach(snake, crates)
        if puzzle.exits & region:
            return moves
        entered = {numbers.get(cell) for cell in region} - done
        done |= entered
        stage = _stage(puzzle, numbers, done, entered, crates, snake, limit)
        if stage is None:
            return None
        crates, snake, found = stage
        moves += found


def _stage(puzzle, numbers, done, entered, crates, snake, limit):
    """Breadth first from (crates, snake) until a room not in `done` or the exit is in reach, pushing the crates of the
    rooms just `entered` (or, when they have none, of every room in reach)."""

    def key(crates, region):
        return crates, min(region)

    region = puzzle.reach(snake, crates)
    here = entered if any(numbers.get(crate) in entered for crate in crates) else {numbers.get(c) for c in region}
    previous = {key(crates, region): None}
    queue = deque([(crates, region, snake)])
    while queue and len(previous) < limit:
        crates, region, snake = queue.popleft()
        if puzzle.exits & region or {numbers.get(cell) for cell in region} - done:
            moves, state = [], key(crates, region)
            while previous[state] is not None:
                state, move = previous[state]
                moves.append(move)
            return crates, snake, moves[::-1]
        for crate in crates:
            if numbers.get(crate) not in here:
                continue
            for name, d in DIRECTIONS.items():
                after = puzzle.push(crates, region, crate, d)
                ahead = (crate[0] + d[0], crate[1] + d[1])
                if after is None or dead(puzzle, ahead):
                    continue
                new_region = puzzle.reach(crate, after)
                state = key(after, new_region)
                if state not in previous:
                    previous[state] = (key(crates, region), (crate, name))
                    queue.append((after, new_region, crate))
    return None


def merge(moves: list[tuple]) -> list[list]:
    """Pushes of one crate on in the same direction become one step: [[x, y], direction, cells]."""
    steps: list[list] = []
    for crate, name in moves:
        d = DIRECTIONS[name]
        last = steps[-1] if steps else None
        if last and last[1] == name and (last[0][0] + d[0] * last[2], last[0][1] + d[1] * last[2]) == crate:
            last[2] += 1
        else:
            steps.append([list(crate), name, 1])
    return steps


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("action", choices=("check", "solve"))
    parser.add_argument("puzzle", type=Path)
    parser.add_argument("level", type=Path, nargs="?", help="check: the level file with the plan")
    args = parser.parse_args()
    puzzle = Puzzle(read(args.puzzle))
    if args.action == "check":
        import omegaconf

        plan = omegaconf.OmegaConf.to_container(omegaconf.OmegaConf.load(args.level).plan)
        problems = check(puzzle, plan)
        print("\n".join(problems) or "the plan works")
        sys.exit(1 if problems else 0)
    moves = solve(puzzle)
    if moves is None:
        sys.exit("no solution found")
    for step in merge(moves):
        print(f"      - push: [{step[0]}, {step[1]}, {step[2]}]")


if __name__ == "__main__":
    main()
