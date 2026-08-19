"""Connectivity-aware molecule grouping via MDAnalysis's bond-guessing plus
fragment detection.

Used specifically for the cleanup tool's "extract one molecule" mode. A
residue-instance heuristic (pick one residue by name and sequence number)
can't tell a genuinely single-residue molecule apart from one monomer of a
much longer chain split across many identically-named residues (e.g. every
unit of a P3HT polymer is its own "P3HT" residue) - and residue numbers
aren't guaranteed unique across independently-built chains in the same box
either, so two unrelated molecules can collide on "residue 1". Bond
connectivity is what actually defines "one molecule", regardless of how its
residues happen to be named or numbered - MDAnalysis already solves this
correctly, so this module leans on it instead of extending our own
hand-rolled residue-based parsing in structure_files.py.
"""

from __future__ import annotations

import re
import warnings
from pathlib import Path

import MDAnalysis as mda
from MDAnalysis.guesser.default_guesser import DefaultGuesser

from gromacs_gui.gmx.structure_files import AtomPosition

_UNKNOWN_VDW_TYPES_RE = re.compile(r"vdw radii for types: (.+?)\. These can be defined")

# Angstrom, roughly carbon-sized. Only affects the distance cutoff used to
# *guess* bonds for atom types MDAnalysis doesn't recognize (common with
# coarse-grained/custom force fields) - never anything physically
# simulated, so an approximate fallback is fine here.
_FALLBACK_VDW_RADIUS = 1.7

# Bounded retry count: each retry only adds newly-reported unknown types, so
# this just needs to be >= the number of distinct unrecognized atom types
# in a file, which is always small in practice.
_MAX_VDW_RETRY_ROUNDS = 50


def compute_fragments(structure_path: Path) -> list[mda.core.groups.AtomGroup]:
    """Load structure_path and return one AtomGroup per connected molecule."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        universe = mda.Universe(str(structure_path))
        bonds = _guess_bonds_with_fallback(universe)
        universe.add_TopologyAttr("bonds", bonds)
    return list(universe.atoms.fragments)


def _guess_bonds_with_fallback(universe: mda.Universe) -> list[tuple[int, int]]:
    """Uses the box explicitly (periodic-aware capped distance search)
    rather than the AtomGroup.guess_bonds() convenience method, which
    doesn't expose a box parameter at all and is 30-70x slower as a
    result (measured on real files: 21s -> 0.3s for ~23k atoms, 45s -> 1.7s
    for ~214k atoms) - not just periodic correctness, but the difference
    between this being safe to run synchronously and needing a background
    thread.
    """
    vdwradii_overrides: dict[str, float] = {}
    for _ in range(_MAX_VDW_RETRY_ROUNDS):
        try:
            guesser = DefaultGuesser(
                universe, vdwradii=vdwradii_overrides or None, box=universe.dimensions
            )
            return guesser.guess_bonds(universe.atoms, universe.atoms.positions)
        except ValueError as exc:
            unknown = _parse_unknown_vdw_types(str(exc))
            new_types = unknown - set(vdwradii_overrides)
            if not new_types:
                raise
            for name in new_types:
                vdwradii_overrides[name] = _FALLBACK_VDW_RADIUS
    raise RuntimeError("Too many distinct unrecognized atom types for bond guessing")


def _parse_unknown_vdw_types(message: str) -> set[str]:
    match = _UNKNOWN_VDW_TYPES_RE.search(message)
    if not match:
        return set()
    return {name.strip() for name in match.group(1).split(",")}


def first_fragment_with_residue(
    fragments: list[mda.core.groups.AtomGroup], residue_names: set[str]
) -> mda.core.groups.AtomGroup | None:
    """The first fragment (in fragment-list order) containing at least one
    atom whose residue name is in residue_names.
    """
    for fragment in fragments:
        if set(fragment.resnames) & residue_names:
            return fragment
    return None


def fragment_to_atom_positions(fragment: mda.core.groups.AtomGroup) -> list[AtomPosition]:
    """MDAnalysis normalizes coordinates to angstrom for both .pdb and .gro
    sources, matching AtomPosition's own always-angstrom convention.
    """
    return [
        AtomPosition(
            atom.resname, atom.name, str(atom.resid), float(pos[0]), float(pos[1]), float(pos[2])
        )
        for atom, pos in zip(fragment.atoms, fragment.positions, strict=True)
    ]
