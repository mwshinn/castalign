from importlib.metadata import PackageNotFoundError, version as _pkg_version

from .base import *
from .graph import Graph, load
from .graph import TransformGraph # Backward compatibility

try:
    __version__ = _pkg_version("castalign")
except PackageNotFoundError:
    # Not installed, e.g. Read the Docs imports directly from the source tree
    __version__ = "0.0.0+unknown"

import PIL.Image as _PILI
_PILI.MAX_IMAGE_PIXELS = 1000000000
