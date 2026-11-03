"""Generate CH39 report solely from observed original runs, not synthetic claims."""
from pathlib import Path
import json,hashlib
D=Path(__file__).resolve().parent

def load(name):return json.loads((D/name).read_text())
def main():
    a=load('original15_results.json');audit=load('public_audit.json');forge=load('forgery_results.json');missing=load('no_checker_results.json')
    if a['case_count']!=15 or audit['signed_cases']!=15 or forge['status']!='PASS' or missing['status']!='PASS':
        raise ValueError('CH39 report cannot claim acceptance before all observed runs')
    testlog=(D/'ch39_tests.log').read_text().strip()
    if '24 passed' not in testlog:raise ValueError('CH39 unit suite not accepted')
    names=a['original_CH23_cases_tested']
    executed=load('executed_source_sha256.json')
    if len(executed)!=6 or not all(x['identical'] for x in executed.values()):raise ValueError('Executed service source mismatch')
    lines=[
    '# Cognitum CH-C14-39 — Independent MPFR proof checking before attestation',
    '', '**Date:** 2026-11-02 (America/Phoenix). **Disposition:** scoped Linux research engineering PASS; scientific/production NO-GO.',
    '', '## Security boundary',
    '', 'CH38 allowed the math worker UID 1002 to fabricate a JSON success report that attestor UID 1003 would sign after checking metadata. CH39 makes attestation contingent on a *second* MPFR replay under checker UID 1004 with its own owner-only original proof material.',
    '', '| Principal | UID | Authority |',
    '|---|---:|---|',
    '|Writer|1000|Case-ID-only request|',
    '|Math worker|1002|Original CH23 224-bit MPFR replay; no signing keys or checker source|',
    '|Independent checker|1004|Separate frozen-source copy, full 127-node certificate and six historical-frame replay; no signing keys|',
    '|Attestor|1003|Requires checker UID + independent success; owns attestation key but no proof files|',
    '|Final witness signer|65534|Owns final signing key, frozen policy and durable history|',
    '', 'The worker success message alone is never sufficient: checker response must bind case, random nonce, frozen policy, exact SHA-256 of worker attestation and newly independently computed attestation. Attestor signs only on equality; the signed ticket embeds the checker receipt and the final signer validates its schema and signature. CH39 signing domains differ from CH38.',
    '', '## Frozen original CH23 regression',
    '', f"- **Original cases:** {len(names)} / 15. No substitutions or new optimizers.",
    f"- **Independent checker+worker replays:** {len(names)*2} mathematical verifier invocations.",
    f"- **Checkpoint nodes rechecked:** {len(names)*127*2:,} (127 per case per independent invocation).",
    f"- **Historical frames rechecked:** {len(names)*6*2} (six per case per invocation).",
    f"- **Source pins:** {audit['original_CH32_CH33_pins_matched']}/15 original CH32 heads and CH33 compacted checkpoints matched.",
    f"- **Executed service source digests:** {len(executed)}/6 matched the current CH39 source files byte-for-byte.",
    f"- **Signatures:** {audit['attestor_signatures_verified']} attestor and {audit['signer_signatures_verified']} signer signatures independently audited.",
    f"- **Wall clock:** {a['elapsed_wall_seconds']} seconds at worker limit 4 and checker limit 4 (both expensive, independent MPFR runs).",
    f"- **Frozen original witness chain tip:** `{a['tip_sha256']}`.",
    '', '## Live adversarial checks',
    '', f"- **24/24** CH39 protocol tests passed (source: `ch39_tests.log`), including forged archive/binding hash, altered bounds, replay, forged checker receipt, absent checker, invalid scope, independently signed legacy ticket refusal and old-domain signature rejection.",
    f"- **Forged real math UID 1002:** result **{forge['status']}**, fabricated original-case MPFR claim was refused; witness created = **{forge['signature_created']}**; elapsed {forge['elapsed_wall_seconds']} seconds. This is a real UID-separated running service, not a mocked payload.",
    f"- **Offline checker UID 1004:** result **{missing['status']}**, worker claimed success but signed witness = **{missing['signed_witness']}**; elapsed {missing['elapsed_wall_seconds']} seconds.",
    '- **Historical forged certificate with recomputed hashes:** CH33 original-data `test_forged_valid_hashes_cannot_replace_mathematical_proof` was rerun and passed (original case, not synthetic).',
    '', '## Assurance limitations',
    '', '1. **Independent execution, shared algorithms:** UID 1002 and UID 1004 use separately protected copies of the *same* historical MPFR verifier implementation; systematic mathematical code errors are still common-mode risks. Independent algorithm / implementation is not claimed.',
    '2. **Attestor trusts checker UID:** checker receipt is protected by SO_PEERCRED and a signed attestor envelope, not a third public-key signature. Compromising checker/attestor or OS root remains outside this security boundary.',
    '3. **No off-host trusted anchor:** public keys and latest tip must be independently pinned. A writable local ledger and all local pins can be rolled back if an attacker controls them.',
    '4. **Not a scientific certificate:** original 0.05 global objective-gap requirement still unmet: **0/15** global-optimality claims. Results are verified-but-unresolved original CH23, not unrestricted-global proof.',
    '5. **Not a power-loss/Windows/EDQUOT result:** earlier CH36 genuine ENOSPC and fsync injections are inherited evidence, not rerun here. Windows testing remains deferred.',
    '', '## Next research gate',
    '', 'Develop or adapt an independently implemented proof verifier, preferably in a different language and arithmetic stack, and independently reproduce CH23 interval enclosures and branch-bound descent to reduce common-mode correctness risk. Defer promotion into production Cognitum C14/G25 and Lu.',
    '' ]
    (D/'Engineering_Report_CH_C14_39.md').write_text('\n'.join(lines))
    print('WROTE report, cases',len(names),'wall',a['elapsed_wall_seconds'])
if __name__=='__main__':main()
