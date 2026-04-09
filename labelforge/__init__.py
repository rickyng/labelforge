"""LabelForge — Professional PDF text label editor.

Workflow:
    1. labelforge analyze input.pdf --output labels.json
    2. Edit new_text fields in labels.json
    3. labelforge apply input.pdf labels.json --output output.pdf
"""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__: str = version("labelforge")
except PackageNotFoundError:
    __version__ = "0.0.0-dev"

__all__ = ["__version__"]
