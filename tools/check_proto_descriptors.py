"""Compare checked-in Protobuf binding descriptors with compiler-produced .proto.

Usage: python tools/check_proto_descriptors.py compiled_cognitum.pb
Run protoc first: python -m grpc_tools.protoc -Iproto
  --descriptor_set_out=compiled_cognitum.pb proto/cognitum/v1/capability.proto

Compiler output may add synthetic JSON-name metadata; compare wire-shape
semantics, field numbers, presence, and oneofs without comparing raw hashes.
"""
from pathlib import Path
import sys

from google.protobuf.descriptor_pb2 import FileDescriptorProto, FileDescriptorSet
from cognitum.proto import physics_linear_motion_pb2
from cognitum.proto import spatial_functional_material_p11_p12_pb2, spatial_functional_material_p8_p10_pb2, spatial_functional_material_p5_p7_pb2, spatial_functional_material_p4_pb2, spatial_functional_material_p3_pb2, spatial_functional_material_p2_pb2, spatial_functional_material_pb2, spatial_host_recovery_readiness_pb2, spatial_durable_incremental_volume_pb2, spatial_incremental_volume_pb2, spatial_map_lifecycle_pb2, spatial_dynamic_scene_robustness_pb2, spatial_dynamic_scene_mapping_pb2
from cognitum.proto import spatial_object_aware_volume_pb2
from cognitum.proto import spatial_temporal_consistency_pb2, spatial_correlated_fusion_pb2, spatial_calibrated_depth_pb2, capability_pb2, ce_handoff_pb2, worker_pb2, supervisor_acceptance_pb2, evaluation_pb2, benchmark_pb2, collector_pb2, specialists_pb2, memory_pb2, state_pb2, interpretation_pb2, formal_pb2, formal_backend_pb2, formal_advanced_pb2, optimization_pb2, workflows_pb2, optimization_runtime_pb2, planning_pb2, planning_engines_pb2, planning_stochastic_pb2, planning_structured_pb2, planning_guidance_pb2, probability_pb2, probability_backend_pb2, probability_continuous_pb2, probability_conjugate_pb2, probability_diagnostics_pb2, causal_pb2, causal_estimation_pb2, causal_dowhy_pb2, causal_heterogeneity_pb2, causal_discovery_pb2, causal_mature_pb2, causal_validation_pb2, causal_stability_pb2, causal_ambiguity_pb2, causal_temporal_pb2, causal_temporal_scm_pb2, causal_temporal_diagnostics_pb2, causal_temporal_advanced_pb2, causal_temporal_discovery_pb2, causal_uncertainty_pb2, causal_interval_comparison_pb2, causal_assurance_policy_pb2, causal_holdout_assurance_pb2, causal_adversarial_assurance_pb2, causal_integrated_assurance_pb2, causal_genuine_worker_assurance_pb2, causal_llm_caller_evaluation_pb2, spatial_scene_pb2, spatial_appearance_pipeline_pb2, spatial_structural_reconciliation_pb2, spatial_structural_c07_bridge_pb2, spatial_ontology_subset_pb2, spatial_identity_pb2, spatial_temporal_pb2, spatial_composition_pb2, spatial_volume_pb2, spatial_appearance_pb2, spatial_structural_audit_pb2, assembly_pb2, ray_occupancy_pb2, structural_hypotheses_pb2, temporal_occupancy_pb2, benchmark_observation_pb2

EXPECTED = {
    "cognitum/physics/v1/linear_motion.proto": physics_linear_motion_pb2.DESCRIPTOR,
    "cognitum/spatial/v1/functional_material_p11_p12.proto": spatial_functional_material_p11_p12_pb2.DESCRIPTOR,
    "cognitum/spatial/v1/functional_material_p8_p10.proto": spatial_functional_material_p8_p10_pb2.DESCRIPTOR,
    "cognitum/spatial/v1/functional_material_p5_p7.proto": spatial_functional_material_p5_p7_pb2.DESCRIPTOR,
    "cognitum/spatial/v1/functional_material_p4.proto": spatial_functional_material_p4_pb2.DESCRIPTOR,
    "cognitum/spatial/v1/functional_material_p3.proto": spatial_functional_material_p3_pb2.DESCRIPTOR,
    "cognitum/spatial/v1/functional_material_p2.proto": spatial_functional_material_p2_pb2.DESCRIPTOR,
    "cognitum/spatial/v1/functional_material.proto": spatial_functional_material_pb2.DESCRIPTOR,
    "cognitum/spatial/v1/host_recovery_readiness.proto": spatial_host_recovery_readiness_pb2.DESCRIPTOR,
    "cognitum/spatial/v1/durable_incremental_volume.proto": spatial_durable_incremental_volume_pb2.DESCRIPTOR,
    "cognitum/spatial/v1/incremental_volume.proto": spatial_incremental_volume_pb2.DESCRIPTOR,
    "cognitum/spatial/v1/map_lifecycle.proto": spatial_map_lifecycle_pb2.DESCRIPTOR,
    "cognitum/spatial/v1/dynamic_scene_robustness.proto": spatial_dynamic_scene_robustness_pb2.DESCRIPTOR,
    "cognitum/spatial/v1/dynamic_scene_mapping.proto": spatial_dynamic_scene_mapping_pb2.DESCRIPTOR,
    "cognitum/spatial/v1/temporal_consistency.proto": spatial_temporal_consistency_pb2.DESCRIPTOR,
    "cognitum/spatial/v1/object_aware_volume.proto": spatial_object_aware_volume_pb2.DESCRIPTOR,
    "cognitum/spatial/v1/correlated_fusion.proto": spatial_correlated_fusion_pb2.DESCRIPTOR,
    "cognitum/spatial/v1/calibrated_depth.proto": spatial_calibrated_depth_pb2.DESCRIPTOR,
    "cognitum/v1/capability.proto": capability_pb2.DESCRIPTOR,
    "cognitum/v1/ce_handoff.proto": ce_handoff_pb2.DESCRIPTOR,
    "cognitum/worker/v1/worker.proto": worker_pb2.DESCRIPTOR,
    "cognitum/security/v1/supervisor_acceptance.proto": supervisor_acceptance_pb2.DESCRIPTOR,
    "cognitum/eval/v1/evaluation.proto": evaluation_pb2.DESCRIPTOR,
    "cognitum/benchmark/v1/benchmark.proto": benchmark_pb2.DESCRIPTOR,
    "cognitum/benchmark/v1/collector.proto": collector_pb2.DESCRIPTOR,
    "cognitum/math/v1/specialists.proto": specialists_pb2.DESCRIPTOR,
    "cognitum/memory/v1/evidence.proto": memory_pb2.DESCRIPTOR,
    "cognitum/state/v1/events.proto": state_pb2.DESCRIPTOR,
    "cognitum/state/v1/interpretation.proto": interpretation_pb2.DESCRIPTOR,
    "cognitum/formal/v1/solve.proto": formal_pb2.DESCRIPTOR,
    "cognitum/formal/v1/backend.proto": formal_backend_pb2.DESCRIPTOR,
    "cognitum/formal/v1/advanced.proto": formal_advanced_pb2.DESCRIPTOR,
    "cognitum/optimization/v1/optimize.proto": optimization_pb2.DESCRIPTOR,
    "cognitum/optimization/v1/workflows.proto": workflows_pb2.DESCRIPTOR,
    "cognitum/optimization/v1/runtime.proto": optimization_runtime_pb2.DESCRIPTOR,
    "cognitum/planning/v1/classical.proto": planning_pb2.DESCRIPTOR,
    "cognitum/planning/v1/engines.proto": planning_engines_pb2.DESCRIPTOR,
    "cognitum/planning/v1/stochastic.proto": planning_stochastic_pb2.DESCRIPTOR,
    "cognitum/planning/v1/structured.proto": planning_structured_pb2.DESCRIPTOR,
    "cognitum/planning/v1/guidance.proto": planning_guidance_pb2.DESCRIPTOR,
    "cognitum/probability/v1/inference.proto": probability_pb2.DESCRIPTOR,
    "cognitum/probability/v1/backend.proto": probability_backend_pb2.DESCRIPTOR,
    "cognitum/probability/v1/continuous.proto": probability_continuous_pb2.DESCRIPTOR,
    "cognitum/probability/v1/conjugate.proto": probability_conjugate_pb2.DESCRIPTOR,
    "cognitum/probability/v1/diagnostics.proto": probability_diagnostics_pb2.DESCRIPTOR,
    "cognitum/causal/v1/scm.proto": causal_pb2.DESCRIPTOR,
    "cognitum/causal/v1/estimation.proto": causal_estimation_pb2.DESCRIPTOR,
    "cognitum/causal/v1/dowhy.proto": causal_dowhy_pb2.DESCRIPTOR,
    "cognitum/causal/v1/heterogeneity.proto": causal_heterogeneity_pb2.DESCRIPTOR,
    "cognitum/causal/v1/discovery.proto": causal_discovery_pb2.DESCRIPTOR,
    "cognitum/causal/v1/mature_worker.proto": causal_mature_pb2.DESCRIPTOR,
    "cognitum/causal/v1/validation.proto": causal_validation_pb2.DESCRIPTOR,
    "cognitum/causal/v1/stability.proto": causal_stability_pb2.DESCRIPTOR,
    "cognitum/causal/v1/ambiguity.proto": causal_ambiguity_pb2.DESCRIPTOR,
    "cognitum/causal/v1/temporal.proto": causal_temporal_pb2.DESCRIPTOR,
    "cognitum/causal/v1/temporal_scm.proto": causal_temporal_scm_pb2.DESCRIPTOR,
    "cognitum/causal/v1/temporal_diagnostics.proto": causal_temporal_diagnostics_pb2.DESCRIPTOR,
    "cognitum/causal/v1/temporal_advanced.proto": causal_temporal_advanced_pb2.DESCRIPTOR,
    "cognitum/causal/v1/temporal_discovery.proto": causal_temporal_discovery_pb2.DESCRIPTOR,
    "cognitum/causal/v1/uncertainty.proto": causal_uncertainty_pb2.DESCRIPTOR,
    "cognitum/causal/v1/interval_comparison.proto": causal_interval_comparison_pb2.DESCRIPTOR,
    "cognitum/causal/v1/assurance_policy.proto": causal_assurance_policy_pb2.DESCRIPTOR,
    "cognitum/causal/v1/holdout_assurance.proto": causal_holdout_assurance_pb2.DESCRIPTOR,
    "cognitum/causal/v1/adversarial_assurance.proto": causal_adversarial_assurance_pb2.DESCRIPTOR,
    "cognitum/causal/v1/integrated_assurance.proto": causal_integrated_assurance_pb2.DESCRIPTOR,
    "cognitum/causal/v1/genuine_worker_assurance.proto": causal_genuine_worker_assurance_pb2.DESCRIPTOR,
    "cognitum/causal/v1/llm_caller_evaluation.proto": causal_llm_caller_evaluation_pb2.DESCRIPTOR,
    "cognitum/spatial/v1/structural_reconciliation.proto": spatial_structural_reconciliation_pb2.DESCRIPTOR,
    "cognitum/spatial/v1/structural_c07_bridge.proto": spatial_structural_c07_bridge_pb2.DESCRIPTOR,
    "cognitum/spatial/v1/ontology_subset.proto": spatial_ontology_subset_pb2.DESCRIPTOR,
    "cognitum/spatial/v1/scene.proto": spatial_scene_pb2.DESCRIPTOR,
    "cognitum/spatial/v1/appearance_pipeline.proto": spatial_appearance_pipeline_pb2.DESCRIPTOR,
    "cognitum/spatial/v1/identity.proto": spatial_identity_pb2.DESCRIPTOR,
    "cognitum/spatial/v1/temporal.proto": spatial_temporal_pb2.DESCRIPTOR,
    "cognitum/spatial/v1/composition.proto": spatial_composition_pb2.DESCRIPTOR,
    "cognitum/spatial/v1/volume.proto": spatial_volume_pb2.DESCRIPTOR,
    "cognitum/spatial/v1/appearance.proto": spatial_appearance_pb2.DESCRIPTOR,
    "cognitum/spatial/v1/structural_audit.proto": spatial_structural_audit_pb2.DESCRIPTOR,
    "cognitum/spatial/v1/assembly.proto": assembly_pb2.DESCRIPTOR,
    "cognitum/spatial/v1/ray_occupancy.proto": ray_occupancy_pb2.DESCRIPTOR,
    "cognitum/spatial/v1/structural_hypotheses.proto": structural_hypotheses_pb2.DESCRIPTOR,
    "cognitum/spatial/v1/temporal_occupancy.proto": temporal_occupancy_pb2.DESCRIPTOR,
    "cognitum/spatial/v1/benchmark_observation.proto": benchmark_observation_pb2.DESCRIPTOR,
}


def normalized_field(field):
    return (
        field.name, field.number, field.type, field.label, field.type_name,
        field.proto3_optional,
        field.oneof_index if field.HasField("oneof_index") else None,
    )


def normalized_file(descriptor):
    return {
        "name": descriptor.name,
        "package": descriptor.package,
        "syntax": descriptor.syntax,
        "enums": {e.name: tuple((v.name, v.number) for v in e.value) for e in descriptor.enum_type},
        "messages": {
            msg.name: {
                "fields": tuple(normalized_field(f) for f in msg.field),
                "oneofs": tuple(o.name for o in msg.oneof_decl),
                "reserved_ranges": tuple((r.start, r.end) for r in msg.reserved_range),
            }
            for msg in descriptor.message_type
        },
    }


def main(filename):
    produced = FileDescriptorSet()
    produced.ParseFromString(Path(filename).read_bytes())
    if len(produced.file) != 1:
        raise SystemExit("expected one compiled .proto source")
    file_name = produced.file[0].name
    if file_name not in EXPECTED:
        raise SystemExit("unexpected compiled protobuf schema name")
    shipped = FileDescriptorProto.FromString(EXPECTED[file_name].serialized_pb)
    if normalized_file(produced.file[0]) != normalized_file(shipped):
        raise SystemExit("checked-in protobuf bindings differ from compiler .proto wire schema")
    print("Protobuf source/binding schema matches: package, names, fields, oneofs, optional presence")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: check_proto_descriptors.py compiled_cognitum.pb")
    main(sys.argv[1])
