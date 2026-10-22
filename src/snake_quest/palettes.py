"""Snake colour schemes the player can pick in the customize screen. Colours are Pyxel palette indices."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Palette:
    """A snake's colours: the head's and the body's, repeated along it."""

    name: str
    head: int
    body: tuple[int, ...]  # repeated along the body, segment by segment: also makes the patterns (bands, diamonds)
    eyes: int = 0  # light ones on a dark head
    gloss: bool = True  # a lighter pixel along the back of every segment


PALETTES: dict[str, Palette] = {
    p.name: p
    for p in (
        Palette("Classic", head=7, body=(11, 11, 4, 3, 3)),
        Palette("Ocean", head=7, body=(12, 12, 6, 5, 5)),
        Palette("Ghost", head=7, body=(13, 13, 6, 13, 7)),
        # patterns: diamonds down the back, saddles, rings (never colour 0 in them: the floor's)
        Palette("Rattler", head=15, body=(15, 15, 4, 9, 4, 15, 15)),
        Palette("Magma", head=9, body=(8, 8, 2, 10, 2, 8, 8)),
        Palette("Leopard", head=15, body=(4,) * 4 + (10,) * 8),
        Palette("Krait", head=6, body=(6, 6, 6, 1, 1)),
        Palette("Mint", head=11, body=(11, 11, 11, 1, 7, 1)),
    )
}
DEFAULT_PALETTE = "Classic"


def palette(name: str) -> Palette:
    """Palette by name, falling back to the default for unknown names (e.g. from an old profile)."""
    return PALETTES.get(name, PALETTES[DEFAULT_PALETTE])
