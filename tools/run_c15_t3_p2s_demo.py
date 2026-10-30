"""Reproducible synthetic cross-capture occupancy change demonstration (NOT sensor data)."""
import json
from cognitum.spatial_temporal_consistency import reconcile, verify
from tests.test_c15_t3_p2s_temporal_consistency import request, cell


def main():
    cases = {
        'same_occupied_capture_sequence': (True, True),
        'new_opposition_pending': (True, True, False),
        'two_free_confirmed_not_forwarded': (True, True, False, False),
        'three_free_recovered_hypothesis': (True, True, False, False, False),
        'recovered_occupied': (False, False, True, True, True),
    }
    results = []
    for scenario, sequence in cases.items():
        q = request(sequence)
        out = reconcile(q)
        verify(q, out)
        c = cell(out)
        results.append({
            'scenario': scenario,
            'capture_ticks': [p.depth.pixels[0].tick for p in q.captures],
            'recovered_state': c.state,
            'state_name': c.DESCRIPTOR.fields_by_name['state'].enum_type.values_by_number[c.state].name,
            'observed_frames': c.observed_capture_count,
            'latest_consecutive_evidence_count': c.latest_consistent_streak,
            'proposed_change_tick': c.change_candidate_tick,
            'change_confirmed_by_streak_heuristic': c.change_confirmed,
            'baseline_probability': c.baseline_probability,
            'adjusted_probability': c.adjusted_probability,
            'target_is_T2_prediction_only': any((x.x,x.y,x.z)==(4,4,6) for x in out.hypothetical_volume.evidence),
            'request_sha256': out.request_sha256.hex(),
        })
    return {
        'milestone': 'C15 T3 P2S',
        'data': 'synthetic caller-declared depth rays',
        'physical_calibration': 'not performed',
        'cross_capture_independence': 'not established',
        'models': {'temporal_half_life_ticks': 1000.,'historical_retention_after_change': .05,
                   'consecutive_readings_required_for_transition': 2,
                   'additional_readings_to_forward_hypothesis': 1},
        'results': results,
        'real_world_accuracy': 'not tested',
        'canonical_or_authority_changes': False,
    }


if __name__ == '__main__':
    print(json.dumps(main(),indent=2,sort_keys=True))
