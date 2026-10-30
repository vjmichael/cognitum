"""G4 offline source admission tests. No third-party runtime claims."""
import importlib.util
import stat
import tempfile
import unittest
import zipfile
from pathlib import Path
from tools.inspect_c14_vendor_archives import inspect_archive, dependency_inventory


def make(path, *, package="causal-learn", extra=None, variant="normal"):
    root={"causal-learn":"causal-learn-main", "econml":"EconML-main", "dowhy":"dowhy-main"}[package]
    metadata={"causal-learn":("setup.py", "VERSION = '0.1.4.8'"),
              "econml":("pyproject.toml", "[project]\nname = 'econml'"),
              "dowhy":("pyproject.toml", "[project]\ndynamic = ['version']")}
    filepart={"causal-learn":("setup.py", "VERSION = '0.1.4.8'"),
              "econml":("econml/_version.py", "__version__ = '0.17.0'"),
              "dowhy":("dowhy/__init__.py", "__version__ = '0.0.0'")}
    with zipfile.ZipFile(path, "w") as z:
        meta, content = metadata[package]
        z.writestr(root + "/" + meta, content)
        fp, code = filepart[package]
        if fp != meta: z.writestr(root + "/" + fp, code)
        if variant == "duplicate": z.writestr(root + "/" + meta, content)
        if variant == "traversal": z.writestr(root + "/../outside.py", "# bad")
        if variant == "backslash": z.writestr(root + "\\outside.py", "# bad")
        if variant == "absolute": z.writestr("/etc/passwd", "bad")
        if variant == "multiroot": z.writestr("other/file.py", "bad")
        if variant == "symlink":
            info=zipfile.ZipInfo(root+"/link")
            info.create_system=3
            info.external_attr=(stat.S_IFLNK | 0o777)<<16
            z.writestr(info,"/etc/passwd")
        if variant == "misversion":
            # inserted duplicate is illegal unless version changed in-place
            pass

class VendorArchiveAdmission(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.p=Path(self.temp.name)/"test.zip"

    def test_causal_learn_declared_version(self):
        make(self.p)
        r=inspect_archive(self.p,"causal-learn")
        self.assertTrue(r["safe"])
        self.assertEqual(r["version_state"],"DECLARED_VERSION_MATCH")
        self.assertFalse(r["exact_release_authenticated"])

    def test_econml_declared_version(self):
        make(self.p,package="econml")
        self.assertEqual(inspect_archive(self.p,"econml")["source_declared_version"],"0.17.0")

    def test_dowhy_dynamic_unverified(self):
        make(self.p,package="dowhy")
        r=inspect_archive(self.p,"dowhy")
        self.assertEqual(r["version_state"],"DYNAMIC_VCS_TAG_NOT_PROVEN")
        self.assertFalse(r["exact_release_authenticated"])

    def test_unknown_package_rejected(self):
        make(self.p)
        with self.assertRaisesRegex(ValueError,"Unknown package"):inspect_archive(self.p,"fake")

    def test_duplicate_entry_rejected(self):
        make(self.p,variant="duplicate")
        with self.assertRaisesRegex(ValueError,"DUPLICATE"):inspect_archive(self.p,"causal-learn")

    def test_path_traversal_rejected(self):
        make(self.p,variant="traversal")
        with self.assertRaisesRegex(ValueError,"UNSAFE"):inspect_archive(self.p,"causal-learn")

    def test_absolute_path_rejected(self):
        make(self.p,variant="absolute")
        with self.assertRaisesRegex(ValueError,"UNSAFE"):inspect_archive(self.p,"causal-learn")

    def test_backslash_path_rejected(self):
        make(self.p,variant="backslash")
        with self.assertRaisesRegex(ValueError,"UNSAFE"):inspect_archive(self.p,"causal-learn")

    def test_multiple_roots_rejected(self):
        make(self.p,variant="multiroot")
        with self.assertRaisesRegex(ValueError,"MULTIPLE_ARCHIVE_ROOTS"):inspect_archive(self.p,"causal-learn")

    def test_symlink_reported_not_safe_to_extract(self):
        make(self.p,variant="symlink")
        report=inspect_archive(self.p,"causal-learn")
        self.assertTrue(report["safe"])
        self.assertFalse(report["safe_to_extract_without_filter"])
        self.assertEqual(len(report["excluded_link_entries"]),1)

    def test_missing_metadata_rejected(self):
        with zipfile.ZipFile(self.p,"w") as z:z.writestr("root/readme.md","hi")
        with self.assertRaisesRegex(ValueError,"MISSING_PROJECT_FILE"):inspect_archive(self.p,"causal-learn")

    def test_missing_dependencies_are_distinct_from_archive_presence(self):
        r=dependency_inventory()
        self.assertIn("momentchi2",r["causal-learn"]["available_imports_in_current_interpreter"])
        self.assertIn("sparse",r["econml"]["available_imports_in_current_interpreter"])

    def test_real_uploaded_archives(self):
        fixtures=[("dowhy", "dowhy-main (1).zip"), ("econml", "EconML-main.zip"), ("causal-learn", "causal-learn-main.zip")]
        root=Path("/mnt/data")
        for key, f in fixtures:
            if not (root/f).is_file():continue
            with self.subTest(package=key):
                self.assertTrue(inspect_archive(root/f,key)["safe"])

if __name__=='__main__': unittest.main()
