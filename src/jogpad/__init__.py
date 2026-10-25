"""jogpad: a jog pendant built from a programmable macro pad."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("jogpad")
except PackageNotFoundError:  # running from a source tree without installing
    __version__ = "0.4.0"
