from __future__ import annotations

from zipfile import ZipFile

import pytest

from scripts.prepare_runtime_data import _extract_if_missing, _safe_extract


def test_safe_extract_normalizes_windows_paths(tmp_path):
    archive = tmp_path / "runtime.zip"
    destination = tmp_path / "output"
    with ZipFile(archive, "w") as bundle:
        bundle.writestr("semantic_index\\model_metadata.json", "{}")

    _safe_extract(archive, destination)

    assert (destination / "semantic_index" / "model_metadata.json").read_text() == "{}"


def test_safe_extract_rejects_parent_traversal(tmp_path):
    archive = tmp_path / "unsafe.zip"
    with ZipFile(archive, "w") as bundle:
        bundle.writestr("../outside.txt", "unsafe")

    with pytest.raises(ValueError, match="Unsafe path"):
        _safe_extract(archive, tmp_path / "output")


def test_extract_requires_all_runtime_files(tmp_path):
    archive = tmp_path / "runtime.zip"
    destination = tmp_path / "output"
    first = destination / "first.txt"
    second = destination / "second.txt"
    with ZipFile(archive, "w") as bundle:
        bundle.writestr("first.txt", "one")
        bundle.writestr("second.txt", "two")

    assert _extract_if_missing(archive, destination, (first, second)) is True
    assert _extract_if_missing(archive, destination, (first, second)) is False
