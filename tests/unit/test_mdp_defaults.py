from __future__ import annotations

import pytest

from gromacs_gui.mdp.defaults import load_default_mdp

STAGES = ["em", "nvt", "npt", "production"]


@pytest.mark.parametrize("stage", STAGES)
def test_default_template_loads_and_has_an_integrator(stage):
    mdp = load_default_mdp(stage)

    assert mdp.get("integrator") is not None


def test_em_uses_steepest_descent():
    mdp = load_default_mdp("em")

    assert mdp.get("integrator") == "steep"


@pytest.mark.parametrize("stage", ["nvt", "npt", "production"])
def test_dynamics_stages_use_md_integrator_and_share_a_timestep(stage):
    mdp = load_default_mdp(stage)

    assert mdp.get("integrator") == "md"
    assert mdp.get("dt") == "0.002"


def test_unknown_stage_raises_value_error():
    with pytest.raises(ValueError):
        load_default_mdp("not-a-real-stage")
