"""Snake colour schemes the player can pick in the customize screen. Colours are Pyxel palette indices."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Palette:
    """A snake's colours: the head's and the body's, repeated along it."""

    name: str
    head: int
    body: tuple[int, ...]  # repeated along the body, segment by segment


PALETTES: dict[str, Palette] = {
    p.name: p
    for p in (
        Palette("Classic", head=7, body=(11, 11, 4, 3, 3)),
        Palette("Ember", head=10, body=(9, 9, 8, 8, 4)),
        Palette("Ocean", head=7, body=(12, 12, 6, 5, 5)),
        Palette("Candy", head=7, body=(14, 14, 8, 15, 15)),
        Palette("Ghost", head=7, body=(13, 13, 6, 13, 7)),
        Palette("Royal", head=10, body=(2, 2, 5, 12, 12)),
    )
}
DEFAULT_PALETTE = "Classic"


def palette(name: str) -> Palette:
    """Palette by name, falling back to the default for unknown names (e.g. from an old profile)."""
    return PALETTES.get(name, PALETTES[DEFAULT_PALETTE])
