"""Relocatable, byte-preserved source-capsule capability; no automatic checks."""

from pathlib import Path

from .scripts import autocomplete_frames
from .scripts import capability_contracts
from .scripts import capability_package
from .scripts import capability_registry


ROOT = Path(__file__).resolve().parent
MANIFEST = "landgrab/autocomplete/capabilities/manifests/source-capsule.json"
RAPP_REFERENCE_DIR = ROOT / "vendor/rapp-1"

__all__ = [
    "ROOT",
    "MANIFEST",
    "RAPP_REFERENCE_DIR",
    "autocomplete_frames",
    "capability_contracts",
    "capability_package",
    "capability_registry",
]
