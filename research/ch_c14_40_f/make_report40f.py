"""Generate a truthful CH40-F research acceptance report from fully accepted data."""
from __future__ import annotations
import pathlib,json,hashlib
R=pathlib.Path(__file__).resolve().parent
CASES='''one_event_n160_i00 one_event_n80_i00 quasi_separated_n160_i00 quasi_separated_n80_i00 rare_1pct_n160_i00 rare_1pct_n160_i13 rare_1pct_n80_i00 rare_5pct_n160_i00 rare_5pct_n80_i00 zero_balanced_n160_i00 zero_balanced_n80_i00 zero_imbalanced_n160_i00 zero_imbalanced_n160_i05 zero_imbalanced_n160_i07 zero_imbalanced_n80_i00'''.split()
def main():
 o=json.loads((R/'CH40F_FULL_15_ACCEPTANCE.json').read_text())
 assert o['case_count']==15 and o['full_node_count']==1905 and o['total_checks']['untrusted_caps']==0
 t=o['total_checks']
 assert t['direct_certified']+t['coupled_certified']==1905 and t['inherited_caps_certified']==1905
 assert 'Ran 21 tests' in (R/'logs/research_receipt_tests.log').read_text()
 assert 'Ran 17 tests' in (R/'logs/ch40e_inherited_adversarial17.log').read_text()
 assert (R/'CH40F_RESEARCH_RECEIPT_SCOPE_TEST.json').is_file()
 data=[f'| `{case}` | 127 | {o["cases"][case]["checks"]["direct_certified"]} | {o["cases"][case]["checks"]["coupled_certified"]} | {"certified" if o["cases"][case]["finite_root_gap_certified"] else "unresolved"} |' for case in CASES]
 body=f'''# Cognitum CH40-F — complete original MPFR producer bound certification

**Disposition:** PASS, scoped to original historical finite-root direct, coupled and inherited bound calculations. **Scientific release: NO-GO.**

## Reproduction and evidence

- Original CH39 source/data ZIP externally pinned SHA-256: `{o["source_archive_sha256"]}`.
- Actual historical CH29 MPFR producer arithmetic: **{o["producer_precision_bits"]} bits**; later independent archived MPFR checkpoint replay precision: **{o["archival_replay_precision_bits"]} bits**. The independent CH40-F proof checker uses Fraction and Decimal interval math.
- Frozen CH23 case count: **15/15**; full source-emitted tree count: **{t["nodes"]} original nodes** (127 per dataset).
- Certified direct/Loewner-Fisher producer caps: **{t["direct_certified"]}**; coupled/tangent producer caps: **{t["coupled_certified"]}**; inherited parent caps: **{t["inherited_caps_certified"]}**; **{t["untrusted_caps"]} unsupported caps**.
- All 14 newly generated trees matched the frozen **uninstrumented** historical CH29 producer proof-bearing fields; the CH40-E preaccepted case also matched the original unmodified producer. Timing-only differences are not proof-field differences.
- Inherited CH40-E mathematical/adversarial regression: **17/17 PASS**. CH40-F research receipt scope/refusal tests: **21/21 PASS**. One original 127-node live independent replay and guarded research admission prototype: **PASS**.
- Full source-identity pins and all producer traces and independently recomputed audits are SHA-256 recorded in `CH40F_FULL_15_ACCEPTANCE.json`. The raw traces remain in the reproduction archive, not GitHub.

## Frozen original-case matrix

| Case | Nodes | Direct caps | Coupled caps | Finite-root gap |
|---|---:|---:|---:|---|
'''+ '\n'.join(data)+f'''
| **Total** | **{t["nodes"]}** | **{t["direct_certified"]}** | **{t["coupled_certified"]}** | **Scientific NO-GO** |

## Trust boundary and remaining gates

The separate verifier's accepted bounds are finite-domain local caps only. None of these historical truncated 127-node records proves unrestricted global optimality. Even if a finite root gap were later certified, a separate argument is required for the objective outside the original finite root.

The historical accepted CH29 path used **direct and coupled** caps; there is no accepted Taylor/Newton contraction or stationary-point exclusion in these original traces. CH40-D separately demonstrated independent Taylor/Newton local witness formats, but those research witnesses are not automatically historical MPFR producer events.

`research_receipt40f.py` provides a **fail-closed research-only receipt policy prototype**: exact original source and checkpoint pins, fresh nonce, actual checker result, OS-authenticated UID requirement in the intended future transport, source trace digest and domain-separated scope. No new signing key is held by the math checker. This prototype has not been installed into CH39's actual independent-UID attestor service. The test for forged peer UIDs simulates peer identity; it does not establish live SO_PEERCRED isolation.

**CH40-G:** Integrate a separate checker-side source-trace verifier under UID 1004 with the real CH39 service, preserve the UID 1003 private signing-key separation, inject forged/rollback/offline checker failures, confirm durable signed research-only witness publication, and keep original scientific NO-GO scope. No Cognitum production C14/G25 or Lu modification until independently accepted.
'''
 (R/'Engineering_Report_CH_C14_40_F.md').write_text(body)
 source_files=['producer_batch40f.py','verify_batch40f.py','verify_tail40f.py','baseline_batch40f.py','consolidate40f.py','research_receipt40f.py','windows_readonly40f.py','RUN_CH40F_WINDOWS_READONLY.cmd','package40f.py','make_report40f.py','tests/test_research_receipt40f.py','verify_trace40e.py','rational_kernel40d.py','prepare40e.py','run_trace40e.py','compare_baseline40e.py','source/producer_trace40e.py']
 src={p:hashlib.sha256((R/p).read_bytes()).hexdigest() for p in source_files}
 (R/'CH40F_SOURCE_SHA256.json').write_text(json.dumps(src,sort_keys=True,indent=2)+'\n')
 print('CH40-F REPORT PASS',len(data),'cases',t['nodes'],'nodes',flush=True)
if __name__=='__main__':main()
