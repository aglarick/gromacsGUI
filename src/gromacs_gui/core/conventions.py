"""Conventional output filenames within each step's folder.

Keeping these in one place means the command layer, wizard step widgets, and
tests all agree on them instead of each hardcoding their own copy.
"""

STRUCTURE_GRO = "processed.gro"
BOX_GRO = "boxed.gro"
SOLVATE_GRO = "solvated.gro"
IONS_TPR = "ions.tpr"
IONS_GRO = "ionized.gro"
TOPOLOGY_TOP = "topol.top"
POSRE_ITP = "posre.itp"
