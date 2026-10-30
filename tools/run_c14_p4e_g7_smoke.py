"""Offline replay smoke for C14 P4E G7 evidence (no third-party import needed)."""
from pathlib import Path
import json
from tools.run_c14_p4e_g7_study import verify_study_report

root=Path(__file__).resolve().parents[1]
checks=[]
for n in (300,900):
    report=json.loads((root/'docs/components/causal'/f'P4E-G7-n{n}-seeded-evidence.json').read_text())
    checks.append((f'n{n}_replay',verify_study_report(report)))
    checks.append((f'n{n}_five_by_five',len(report['results'])==25))
    checks.append((f'n{n}_positivity_rejection',sum(r['status']=='PRECHECK_REJECTED' for r in report['results'])==5))
    checks.append((f'n{n}_hidden_graph_guard',sum(r['method_results'].get('dowhy_explicit_latent_graph',{}).get('status')=='BLOCKED_KNOWN_UNOBSERVED_CONFOUNDER' for r in report['results'])==5))
    checks.append((f'n{n}_interaction_exact_reconciliation', all(
        abs(r['method_results']['statsmodels_interaction']['ate']-r['reference']['ate'])<1e-9
        for r in report['results'] if r['status']=='COMPLETE')))
    checks.append((f'n{n}_not_production',not report['scientific_backends']['production_authorization_attested'] and
                   not report['scientific_backends']['dowhy_tag_authenticated']))
for name,ok in checks:
    print(('PASS ' if ok else 'FAIL ')+name)
if not all(ok for _,ok in checks):raise SystemExit(1)
print(f'ALL {len(checks)} G7 OFFLINE REPLAY CHECKS PASSED')
