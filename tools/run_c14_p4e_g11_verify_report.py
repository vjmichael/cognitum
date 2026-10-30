"""Recompute entire holdout + shift study against committed evidence, offline."""
import hashlib,json
from tools import run_c14_p4e_g11_holdout as study
from cognitum import causal_holdout_assurance as gate

def main():
    raw=gate.REPORT_PATH.read_bytes()
    assert hashlib.sha256(raw).hexdigest()==gate.PINNED_G11_SHA256, 'PINNED_REPORT_CHANGED'
    stored=json.loads(raw)
    observed=study.conduct()
    assert observed==stored, 'G11_SYNTHETIC_STUDY_DETERMINISTIC_REPLAY_MISMATCH'
    assert observed['frozen_G10_policy_sha256']==gate.FROZEN_G10_SHA256
    print('PASS full 2,000 holdout and 600 shifted fixture deterministic replay')
    print('PASS pinned G10 policy and G9 calibration provenance')
    print('PASS fixed-seed distribution shift diagnostics reproducible')

if __name__=='__main__':main()
