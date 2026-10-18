"""Snake Quest, a level-based snake game built with Pyxel."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("snake-quest")
except PackageNotFoundError:  # running from a source tree that was never installed
    __version__ = "0.0.0"
