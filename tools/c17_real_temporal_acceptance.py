"""C17 authorized real-source temporal holdout runner (no auto downloads).

Input CSV format: time_ms,value,source_id,observation_id
Caller supplies a single already authorized regular time series; the script
does not fetch any external data, modify Lu memory or create model weights on
disk. Emits provenance digest and aggregate metrics, no raw readings.
"""
from argparse import ArgumentParser
from hashlib import sha256
from pathlib import Path
import csv
import json

from cognitum.temporal_statespace import TemporalSequence,TemporalSample,TemporalModel
from cognitum.temporal_evaluation import evaluate_heldout

MAX_CSV_BYTES=150000
MAX_ROWS=512


def read_source(path:Path,*,origin_id:str,unit:str):
    if not isinstance(path,Path) or not path.is_absolute():
        raise ValueError("authorized absolute benchmark input path required")
    if path.is_symlink() or not path.is_file() or not 0<path.stat().st_size<=MAX_CSV_BYTES:
        raise ValueError("missing, symlinked or oversized temporal source")
    data=path.read_bytes()
    try:
        raw=data.decode("utf-8-sig")
        lines=list(csv.DictReader(raw.splitlines()))
    except (UnicodeError,csv.Error) as exc:
        raise ValueError("malformed CSV encoding") from exc
    if not 24<=len(lines)<=MAX_ROWS:
        raise ValueError("insufficient or oversized temporal dataset")
    if any(set(row)!={"time_ms","value","source_id","observation_id"}
           or None in row for row in lines):
        raise ValueError("unexpected or missing temporal CSV column")
    samples=[]
    for row in lines:
        try:
            if (not row["time_ms"].isdigit() or not row["value"]
                    or row["value"].strip()!=row["value"]):
                raise ValueError("invalid timestamp or measured value")
            number=float(row["value"])
            sample=TemporalSample(int(row["time_ms"]),(number,),
                                  row["source_id"],row["observation_id"])
        except (OverflowError,TypeError,ValueError) as exc:
            raise ValueError("invalid measured source row") from exc
        samples.append(sample)
    seq=TemporalSequence((unit,),tuple(samples),origin_id,"imported","unverified")
    return seq,sha256(data).hexdigest()


def run(path:Path,*,train_count:int,origin_id:str,unit:str,
        admitted_by_trusted_host:bool=False):
    if admitted_by_trusted_host is not True:
        raise PermissionError("authorized real-data evaluation must be host admitted")
    seq,digest=read_source(path,origin_id=origin_id,unit=unit)
    model=TemporalModel("constant_velocity",
                        .002,.08,1.,4.,60000)
    results=evaluate_heldout(
        seq,model,train_count=train_count,
        include_learned=True,host_admitted_training=True)
    output={
        "schema_version":1,
        "status":"EVALUATED_SOURCE_UNAUTHENTICATED_BY_ADAPTER",
        "source_sha256":digest,"origin_id":origin_id,"unit":unit,
        "training_count":train_count,
        "heldout_count":len(seq.samples)-train_count,
        "metrics":[{
            "model":r.model,"sample_count":r.count,
            "mae":r.mae,"rmse":r.rmse,
            "mean_wall_ms":r.mean_wall_ms,
            "nominal_gaussian_coverage_90":r.forecast_coverage_90,
            "ood_count":r.ood_count,
        } for r in results],
        "limitations":[
            "source_authorization_boolean_must_be_verified_by_real_Lu_host",
            "csv_source_license_and_sampling_validity_not_authenticated",
            "results_only_for_this_predeclared_chronological_split",
            "no_Lu_transformer_with_without_comparison",
            "no_raw_user_data_emitted_to_stdout",
            "one_step_teacher_forcing_not_recursive_long_horizon",
            "source_sha256_correlates_not_authenticates",
        ],
    }
    return output


def main():
    ap=ArgumentParser()
    ap.add_argument("--data",required=True)
    ap.add_argument("--train-count",required=True,type=int)
    ap.add_argument("--origin-id",required=True)
    ap.add_argument("--unit",required=True)
    ap.add_argument("--authorized-data-use",action="store_true")
    opts=ap.parse_args()
    print(json.dumps(run(Path(opts.data).absolute(),train_count=opts.train_count,
        origin_id=opts.origin_id,unit=opts.unit,
        admitted_by_trusted_host=opts.authorized_data_use),indent=2,sort_keys=True))


if __name__=="__main__":
    main()
