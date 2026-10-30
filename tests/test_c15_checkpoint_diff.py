"""Source checkpoint reconciliation negative-path tests; local synthetic ZIPs."""
from pathlib import Path
import stat
import sys
import zipfile

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools.c15_checkpoint_diff import diff, inventory, classification, UnsafeCheckpoint


def make_zip(path, entries):
    with zipfile.ZipFile(path, "w") as archive:
        for name, content in entries:
            archive.writestr(name, content)


def test_detects_changed_added_and_deleted(tmp_path):
    a, b = tmp_path / "before.zip", tmp_path / "after.zip"
    make_zip(a, [("cognitum/a.py", "old"), ("tools/old.py", "gone"), ("docs/guide.md", "same")])
    make_zip(b, [("cognitum/a.py", "new"), ("tests/new.py", "add"), ("docs/guide.md", "same")])
    report = diff(a, b)
    assert (report["added"], report["changed"], report["deleted"], report["unchanged"]) == (1, 1, 1, 1)
    assert report["github_repository_compared"] is False
    assert report["github_upload_approved"] is False
    assert all(x["category"] == "source_candidate" for x in report["changes"])


@pytest.mark.parametrize("bad", ["../escape.txt", "/absolute.py", "C:/drive.py", "foo\\bar.py", "x/../y.py"])
def test_rejects_unsafe_path(tmp_path, bad):
    path = tmp_path / "unsafe.zip"
    make_zip(path, [(bad, "bad")])
    with pytest.raises(UnsafeCheckpoint): inventory(path)


def test_rejects_duplicate_entry(tmp_path):
    import warnings
    path = tmp_path / "duplicate.zip"
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        make_zip(path, [("a.py", "one"), ("a.py", "two")])
    with pytest.raises(UnsafeCheckpoint, match="DUPLICATE"): inventory(path)


def test_rejects_symlink(tmp_path):
    path = tmp_path / "symlink.zip"
    item = zipfile.ZipInfo("tools/link.py")
    item.create_system = 3
    item.external_attr = (stat.S_IFLNK | 0o777) << 16
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr(item, "./target")
    with pytest.raises(UnsafeCheckpoint, match="SYMLINK"): inventory(path)


def test_classification_prevents_evidence_autopromotion():
    assert classification("NATIVE_GATE_EVIDENCE/out.log") == "review_checkpoint_evidence"
    assert classification("tools/__pycache__/compiled.pyc") == "excluded_generated"
    assert classification("cognitum/math.py") == "source_candidate"
    assert classification("docs/samples/data.csv") == "review_research_data"


def test_rejects_oversized_zip_member(tmp_path, monkeypatch):
    path = tmp_path / "size.zip"
    make_zip(path, [("code.py", "123456")])
    monkeypatch.setattr("tools.c15_checkpoint_diff.MAX_ENTRY_BYTES", 5)
    with pytest.raises(UnsafeCheckpoint, match="OVERSIZED_ENTRY"): inventory(path)
