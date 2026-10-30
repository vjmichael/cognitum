"""G12 deterministic generator replay plus independent count/aggregate audit."""
import hashlib
import json
from pathlib import Path
from cognitum import causal_adversarial_assurance as gate
from cognitum import causal_g12_independent_verifier as independent
from tools import run_c14_p4e_g12_adversarial as generator


def main():
    raw=gate.REPORT_PATH.read_bytes()
    assert hashlib.sha256(raw).hexdigest()==gate.PINNED_G12_REPORT_SHA256,'FROZEN_EVIDENCE_DIGEST_MISMATCH'
    stored=json.loads(raw)
    independent_result=independent.verify_report(stored)
    assert independent_result['records_verified']==960
    assert generator.conduct()==stored,'G12_GENERATOR_FULL_REPLAY_MISMATCH'
    assert hashlib.sha256(Path(gate.g11.__file__).read_bytes()).hexdigest()==gate.PINNED_G11_SOURCE_SHA256
    print('PASS 960 independent count/math checks, 960 full generator replays, frozen upstream code and report hashes')

if __name__=='__main__':main()
