"""C01 offline CE compatibility fixtures. No Lu installation or activation."""
from dataclasses import replace
import json
from pathlib import Path
import unittest

from cognitum.ce_manifest import ProposedToolBinding, compatibility_fixture
from cognitum.contracts import Effect, Manifest, Operation, Shape, digest
from cognitum.plugins.calculator import Calculator


def calculator_binding(**overrides):
    values = {
        "cognitum_operation": "calc.rational",
        "native_tool_id": "cognitum.calc.rational",
        "model_tool_name": "cognitum_calc_rational",
        "input_type_url": "type.googleapis.com/cognitum.v1.CalculateRationalRequest",
        "output_type_url": "type.googleapis.com/cognitum.v1.CalculateRationalResult",
    }
    values.update(overrides)
    return ProposedToolBinding(**values)


def fixture(manifest=None, bindings=None):
    return compatibility_fixture(
        Calculator().manifest() if manifest is None else manifest,
        "cognitum.calc",
        (calculator_binding(),) if bindings is None else bindings,
    )


class CEFixtureTests(unittest.TestCase):
    def test_disabled_noninstallable_and_nonadvertised_by_default(self):
        result = fixture()
        self.assertEqual(result["fixture_schema"], "cognitum.ce_compatibility.v0")
        self.assertEqual(result["module_kind_proposed"], "optional_core_extension")
        self.assertEqual(result["host_contract_status"], "unbound_proposal_not_host_approved")
        self.assertFalse(result["default_enabled"])
        self.assertFalse(result["model_advertised"])
        self.assertFalse(result["installable"])

    def test_frozen_golden_contract_fixture(self):
        expected = json.loads((Path(__file__).parent / "fixtures" / "ce_calc_v0.json").read_text(encoding="utf-8"))
        self.assertEqual(fixture(), expected)

    def test_exact_calculator_semantics_are_exposed_without_authority(self):
        result = fixture()
        tool, = result["proposed_tools"]
        op, = Calculator().manifest().operations
        self.assertEqual(tool["cognitum_operation"], op.name)
        self.assertEqual(tool["cognitum_operation_schema_version"], op.schema_version)
        self.assertEqual(tool["input_schema_hash_sha256"], digest(op.input.json_schema()))
        self.assertEqual(tool["output_schema_hash_sha256"], digest(op.output.json_schema()))
        self.assertEqual(tool["assurance"], "exact_arithmetic")
        self.assertEqual(tool["declared_effects"], [])
        self.assertEqual(result["source_manifest"]["sha256"],
                         digest(Calculator().manifest().describe()))

    def test_serializes_deterministically_without_secrets(self):
        a = json.dumps(fixture(), sort_keys=True, separators=(",", ":"))
        b = json.dumps(fixture(), sort_keys=True, separators=(",", ":"))
        self.assertEqual(a, b)
        self.assertNotIn("grant", a)
        self.assertNotIn("authorization", a)
        self.assertNotIn("api_key", a)

    def test_bad_tool_names_and_native_id_are_rejected(self):
        for name in ("", "_starts_with_underscore", "includes space", "a" * 65,
                     "cognitum.calc.rational"):
            with self.subTest(name=name), self.assertRaises(ValueError):
                calculator_binding(model_tool_name=name)
        for native_id in ("calc", "Cognitum.calc.rational", "cognitum..calc",
                          "cognitum.Calc.rational", "x" * 129, "cognitum.calc.é"):
            with self.subTest(native_id=native_id), self.assertRaises(ValueError):
                calculator_binding(native_tool_id=native_id)

    def test_bad_protobuf_type_url_is_rejected(self):
        for value in ("", "application/json", "type.googleapis.com/",
                      "type.googleapis.com/lu/v1/Tool", "type.googleapis.com/X.é",
                      "type.googleapis.com/" + "A" * 513):
            with self.subTest(value=value), self.assertRaises(ValueError):
                calculator_binding(input_type_url=value)

    def test_no_implicit_operation_binding_or_ce_namespace_escape(self):
        with self.assertRaises(ValueError):
            fixture(bindings=())
        with self.assertRaises(ValueError):
            fixture(bindings=(calculator_binding(cognitum_operation="unknown"),))
        with self.assertRaises(ValueError):
            fixture(bindings=(calculator_binding(native_tool_id="other.calc.rational"),))
        with self.assertRaises(ValueError):
            compatibility_fixture(Calculator().manifest(), "invalid",
                                  (calculator_binding(),))

    def test_duplicate_bindings_fail_closed(self):
        binding = calculator_binding()
        with self.assertRaises(ValueError):
            fixture(bindings=(binding, binding))

    def test_effectful_component_cannot_be_downgraded_to_inert(self):
        original = Calculator().manifest()
        op, = original.operations
        for effects in (
            (Effect("read_file", "workspace:reports"),),
            (Effect("read_state", "session:a"), Effect("network", "example.com")),
        ):
            with self.subTest(effects=effects), self.assertRaises(ValueError):
                fixture(manifest=replace(original, operations=(replace(op, effects=effects),)))

    def test_untrusted_mapping_forms_cannot_load(self):
        with self.assertRaises(TypeError):
            fixture(manifest={"name": "fake"})
        with self.assertRaises(ValueError):
            fixture(bindings=[calculator_binding()])
        with self.assertRaises(TypeError):
            fixture(bindings=({"model_tool_name": "fake"},))

    def test_multiple_operations_require_one_mapping_each(self):
        original = Calculator().manifest()
        op, = original.operations
        second = replace(
            op, name="calc.second",
            input=Shape((("expression", 10),)),
        )
        new_manifest = replace(original, operations=(op, second))
        with self.assertRaises(ValueError):
            fixture(manifest=new_manifest)
        result = fixture(manifest=new_manifest, bindings=(
            calculator_binding(),
            calculator_binding(
                cognitum_operation="calc.second",
                native_tool_id="cognitum.calc.second",
                model_tool_name="cognitum_calc_second",
            ),
        ))
        self.assertEqual([x["cognitum_operation"] for x in result["proposed_tools"]],
                         ["calc.rational", "calc.second"])


if __name__ == "__main__":
    unittest.main()
