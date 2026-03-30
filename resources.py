"""
Star Citizen resource roster.

SCU_RESOURCES  – mined minerals, quantified in SCU, carry a Quality (0–1000)
UNIT_RESOURCES – gems/rare stones, quantified in Units, no quality
"""

# ── SCU resources (mineable, have Quality) ────────────────────────────────────

SCU_RESOURCES: list[str] = [
    "Agricium",
    "Aluminium",
    "Aslarite",
    "Beryl",
    "Bexalite",
    "Borase",
    "Copper",
    "Corundum",
    "Gold",
    "Hephaestanite",
    "Ice",
    "Iron",
    "Laranite",
    "Lindinium",
    "Ouratite",
    "Quantainium",
    "Quartz",
    "Riccite",
    "Savrilium",
    "Silicon",
    "Stileron",
    "Taranite",
    "Tin",
    "Titanium",
    "Torite",
    "Tungsten",
]

# ── Unit resources (gems, no quality) ─────────────────────────────────────────

UNIT_RESOURCES: list[str] = [
    "Aphorite",
    "Beradom",
    "Carinite",
    "Carinite-Pure",
    "Dolivine",
    "Feynmaline",
    "Glacosite",
    "Hadanite",
    "Jaclium",
    "Janalite",
    "Sadaryx",
    "Saldynium",
]

# ── combined list & helpers ────────────────────────────────────────────────────

ALL_RESOURCES: list[str] = sorted(SCU_RESOURCES + UNIT_RESOURCES, key=str.lower)

_SCU_SET:  set[str] = {r.lower() for r in SCU_RESOURCES}
_UNIT_SET: set[str] = {r.lower() for r in UNIT_RESOURCES}

# Fast search indices
_SCU_INDEX:  list[tuple[str, str]] = [(r.lower(), r) for r in SCU_RESOURCES]
_UNIT_INDEX: list[tuple[str, str]] = [(r.lower(), r) for r in UNIT_RESOURCES]
_ALL_INDEX:  list[tuple[str, str]] = [(r.lower(), r) for r in ALL_RESOURCES]


def is_scu_resource(name: str) -> bool:
    return name.lower() in _SCU_SET


def is_unit_resource(name: str) -> bool:
    return name.lower() in _UNIT_SET


def is_known_resource(name: str) -> bool:
    return is_scu_resource(name) or is_unit_resource(name)


def get_unit_label(name: str) -> str:
    """Return 'SCU' or 'Units' for a given resource name."""
    return "SCU" if is_scu_resource(name) else "Units"


def search_resources(partial: str, only: str = "all") -> list[str]:
    """
    Return up to 25 resource names matching `partial`.
    only: 'scu' | 'units' | 'all'
    """
    needle = partial.lower()
    index = {"scu": _SCU_INDEX, "units": _UNIT_INDEX}.get(only, _ALL_INDEX)
    return [original for lower, original in index if needle in lower][:25]
