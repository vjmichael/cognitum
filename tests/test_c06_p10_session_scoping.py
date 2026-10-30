"""P10 source contract tests; these do not compile/execute the Rust overlay."""
import re
import unittest
from pathlib import Path

GATE = Path(__file__).resolve().parents[1] / (
    "integrations/lu/src-tauri/lu-core/src/ansf_memory_gate.rs"
)


class ScopedHostMutationContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = GATE.read_text(encoding="utf-8")

    def test_mutation_callback_no_longer_escapes_raw_ansf_store(self):
        function = self.source.split("pub fn with_source_mutation", 1)[1].split(
            "pub fn reconcile_source", 1
        )[0]
        self.assertIn("FnOnce(&ScopedAnsfMutation<'_>)", function)
        self.assertNotIn("FnOnce(&AnsfStore)", function)
        self.assertNotIn("mutate(&self.book)", function)
        self.assertIn("session_id: &self.index.session_id", function)
        self.assertIn("mutate(&scoped)", function)

    def test_only_bound_session_id_passed_to_all_mutators(self):
        impl = self.source.split("impl ScopedAnsfMutation<'_>", 1)[1].split(
            "/// ANSF source and index are owned elsewhere", 1
        )[0]
        for method in ("append_entry", "append_edited_entry", "start_chapter", "close_chapter"):
            self.assertIn(f"pub fn {method}(", impl)
        for target in (
            "self.store.append_entry(self.session_id,",
            "self.store.append_edited_entry(\n            self.session_id,",
            "self.store.start_chapter(self.session_id,",
            "self.store.close_chapter(self.session_id,",
            "import_jan_jsonl_with_policy(self.store, self.session_id,",
        ):
            with self.subTest(target=target):
                self.assertIn(target.replace('\n', '\n'), impl)
        self.assertNotIn("pub fn store(", impl)
        self.assertNotIn("pub fn session_id(", impl)

    def test_private_policy_storage_and_symlink_checks_are_in_native_gate(self):
        source = self.source
        self.assertIn("check_policy_storage(policy_path)?", source)
        self.assertIn("std::fs::symlink_metadata(parent)", source)
        self.assertIn("std::fs::symlink_metadata(path)", source)
        self.assertIn("MemoryGateError::InsecureStorage", source)
        self.assertIn("directory.permissions().mode() & 0o077", source)
        self.assertIn("options.read(true).write(true).create(true).mode(0o600)", source)
        self.assertIn("fn insecure_policy_directory_and_symlink_are_rejected()", source)
        self.assertIn("0o644", source)
        self.assertIn("0o755", source)

    def test_scoped_rust_tests_include_multisession_and_rejected_import(self):
        for target in (
            "fn fenced_mutator_is_bound_to_only_one_ansf_session()",
            "fn scoped_import_rejects_cross_session_source_even_inside_fence()",
            "f.book.page_after(\"chat2\", 0, 10)",
            "JanImportPolicy::RejectChangedSource",
            "MemoryGateError::Dirty",
        ):
            with self.subTest(target=target):
                self.assertIn(target.replace('\\\"', '"'), self.source)


if __name__ == "__main__":
    unittest.main()
