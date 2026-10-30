"""Deterministic P2R synthetic correlation study (not calibrated camera data)."""
import json
from cognitum.spatial_correlated_fusion import fuse, verify, SENSITIVITY_RHOS
from tests.test_c15_t3_p2r_correlated_fusion import make, selected


def main():
    results=[]
    for rho in SENSITIVITY_RHOS:
        q=make(rho)
        out=fuse(q)
        verify(q,out)
        cell=selected(out)
        results.append({
            'assumed_correlation':rho,
            'independent_probability':cell.independent_probability,
            'correlation_adjusted_probability':cell.adjusted_probability,
            'correlated_group_size':cell.largest_correlated_group,
            'group_count':cell.capture_group_count,
            'sensitivity_grid_range':[
                cell.sensitivity_min_probability,cell.sensitivity_max_probability],
        })
    report={
        'milestone':'C15 T3 P2R', 'data_kind':'synthetic_caller_declared_depth',
        'sensor_calibration':'not_authenticated', 'research_only':True,
        'physical_occupancy_truth':'not_inferred',
        'baseline':'C15 T3 P2Q independent-ray log odds',
        'model':'same-source/same-frame equicorrelation effective-sample-size heuristic',
        'cells':results,
        'external_benchmark':'not_run',
    }
    print(json.dumps(report,indent=2,sort_keys=True))
    return report


if __name__ == '__main__':main()
