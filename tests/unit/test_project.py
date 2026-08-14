from __future__ import annotations

from gromacs_gui.core.project import Project
from gromacs_gui.core.step_state import StepState


def test_create_project_builds_expected_layout(tmp_path):
    root = tmp_path / "myproj"

    project = Project.create(root)

    assert (root / "topology").is_dir()
    assert (root / "00_structure").is_dir()
    assert (root / "07_production").is_dir()
    assert (root / "project.json").is_file()
    assert project.step_record("structure").state == StepState.PENDING


def test_save_and_reload_roundtrip(tmp_path):
    root = tmp_path / "myproj"
    project = Project.create(root)
    (root / "00_structure" / "processed.gro").write_text("fake gro contents")
    project.manifest.force_field = "amber99sb-ildn"
    project.record_step_started("structure", input_hash="abc123")
    project.record_step_finished("structure", output_files=["00_structure/processed.gro"])

    reopened = Project.open(root)

    assert reopened.manifest.force_field == "amber99sb-ildn"
    record = reopened.step_record("structure")
    assert record.state == StepState.DONE
    assert record.input_hash == "abc123"
    assert record.output_files == ["00_structure/processed.gro"]


def test_finishing_a_step_marks_downstream_done_steps_stale(tmp_path):
    root = tmp_path / "myproj"
    project = Project.create(root)
    project.record_step_finished("structure", output_files=[])
    project.record_step_finished("box", output_files=[])
    assert project.step_record("box").state == StepState.DONE

    # Re-running "structure" (e.g. a different force field) invalidates "box".
    project.record_step_finished("structure", output_files=[])

    assert project.step_record("box").state == StepState.STALE


def test_reconcile_demotes_done_step_with_missing_output_files(tmp_path):
    root = tmp_path / "myproj"
    project = Project.create(root)
    output_file = root / "00_structure" / "processed.gro"
    output_file.write_text("fake gro contents")
    project.record_step_finished("structure", output_files=["00_structure/processed.gro"])

    output_file.unlink()  # simulate the user deleting it by hand
    reopened = Project.open(root)

    record = reopened.step_record("structure")
    assert record.state == StepState.PENDING
    assert record.output_files == []


def test_compute_input_hash_is_stable_and_sensitive_to_content():
    hash_a = Project.compute_input_hash("amber99sb-ildn", "tip3p")
    hash_b = Project.compute_input_hash("amber99sb-ildn", "tip3p")
    hash_c = Project.compute_input_hash("amber99sb-ildn", "spc")

    assert hash_a == hash_b
    assert hash_a != hash_c
