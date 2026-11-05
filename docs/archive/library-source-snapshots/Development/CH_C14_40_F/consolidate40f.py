"""Strict frozen-source CH40-F finalizer: no partial matrix may become PASS."""
from __future__ import annotations
import json,hashlib,pathlib,zipfile,datetime
ROOT=pathlib.Path(__file__).resolve().parent; E=ROOT.parent/'CH_C14_40_E';F=ROOT
CASES='''one_event_n160_i00 one_event_n80_i00 quasi_separated_n160_i00 quasi_separated_n80_i00 rare_1pct_n160_i00 rare_1pct_n160_i13 rare_1pct_n80_i00 rare_5pct_n160_i00 rare_5pct_n80_i00 zero_balanced_n160_i00 zero_balanced_n80_i00 zero_imbalanced_n160_i00 zero_imbalanced_n160_i05 zero_imbalanced_n160_i07 zero_imbalanced_n80_i00'''.split()
PIN='9e713b102982ea09fecbcfbd27bccf55d56808188bfc3e5be1ba76922000ae6b'
def sha(b):return hashlib.sha256(b).hexdigest()
def main():
 arch=E/'Cognitum_CH_C14_39_Independent_MPFR_Checker_Original_CH23_2026-11-02.zip'
 if sha(arch.read_bytes())!=PIN:raise ValueError('Wrong externally pinned CH39 source')
 with zipfile.ZipFile(arch) as z:
  proto=json.loads(z.read('CH_C14_29/frozen_protocol.json'));pins=json.loads(z.read('CH_C14_39/CH39_public_witness/frozen_pins.json'))
  if proto['precision_bits']!=160 or proto['replay_precision_bits']!=224:raise ValueError('Frozen producer/replay arithmetic precision changed')
 cases={};s={'nodes':0,'direct_certified':0,'coupled_certified':0,'inherited_caps_certified':0,'untrusted_caps':0,'coupled_candidates_checked':0}
 prod=json.loads((F/'producer_progress.json').read_text()); ver=json.loads((F/'verifier_progress.json').read_text());base=json.loads((F/'baseline_progress.json').read_text())
 tail_path=F/'verifier_tail_progress.json'
 if tail_path.exists():
  tail=json.loads(tail_path.read_text())
  if set(ver)&set(tail):raise ValueError('Duplicate case assignments to independent verifier shards')
  ver.update(tail)
 if set(prod)!=set(CASES)-{'one_event_n80_i00'} or set(ver)!=set(CASES)-{'one_event_n80_i00'} or set(base)!=set(CASES)-{'one_event_n80_i00'}:raise ValueError('Incomplete 15-case producer/verifier/baseline matrix')
 for case in CASES:
  t=F/'results'/f'{case}_127_original_mpfr_trace.json';a=F/'results'/f'{case}_127_audit.json'
  if not t.is_file() or not a.is_file():raise ValueError('Missing original trace/audit '+case)
  trace=json.loads(t.read_text());audit=json.loads(a.read_text());c=audit['checks']
  if trace['original_archive_sha256']!=PIN or trace['case']!=case or trace['node_count']!=127 or trace['original_case_sha256']!=proto['original_case_sha256'][case]:raise ValueError('Wrong producer identity '+case)
  if audit['case']!=case or not audit['all_recorded_selected_caps_certified'] or audit['global_optimality_certified'] or audit['scientific_release']!='NO_GO' or c['nodes']!=127 or c['untrusted_caps']!=0 or c['inherited_caps_certified']!=127 or c['direct_certified']+c['coupled_certified']!=127:raise ValueError('Original mathematics not independently certified '+case)
  if case!='one_event_n80_i00':
   if ver[case]['status']!='PASS_INDEPENDENT_FINITE_BOUND_CAPS' or prod[case]['status']!='PRODUCER_PASS_PENDING_INDEPENDENT_VERIFIER' or base[case]['status']!='PASS_UNMODIFIED_PROOF_FIELD_EQUIVALENCE':raise ValueError('No corresponding independent verifier and uninstrumented baseline '+case)
   if ver[case]['trace_sha256']!=sha(t.read_bytes()) or base[case]['trace_sha256']!=sha(t.read_bytes()):raise ValueError('Source trace SHA mismatch '+case)
  if case=='one_event_n80_i00':
   if (E/'results'/'full127_unchanged_baseline.exit').read_text().strip()!='0' or 'all certificate proof fields identical' not in (E/'results'/'full127_unchanged_baseline.log').read_text():raise ValueError('Missing accepted CH40-E original baseline equality')
  cases[case]={'status':'PASS_FINITE_ROOT_ORIGINAL_OPTIMIZED_CAPS','node_count':127,'proof_trace_sha256':sha(t.read_bytes()),'proof_trace_bytes':t.stat().st_size,'independent_verifier_sha256':sha(a.read_bytes()),'producer_full_unmodified_equivalence':True,'original_head_sha256':pins[case]['original_head_sha256'],'checkpoint_sha256':pins[case]['checkpoint_sha256'],'finite_root_gap_certified':audit['finite_root_gap_certified'],'scientific_release':'NO_GO','checks':c}
  for k in s:s[k]+=c[k]
 if s['nodes']!=15*127 or s['inherited_caps_certified']!=15*127 or s['untrusted_caps']!=0:raise ValueError('Wrong global matrix sum')
 out={'protocol':'CH40F-FROZEN-ORIGINAL-FULL-127-NODE-PRODUCER-CAP-VERIFICATION-V1','scientific_release':'NO_GO','research_scope_only':True,'ch39_live_attestation_integrated':False,'full_historical_newton_taylor_event_certified':False,'source_archive_sha256':PIN,'producer_precision_bits':160,'archival_replay_precision_bits':224,'case_count':len(CASES),'full_node_count':s['nodes'],'total_checks':s,'all_finite_root_gaps_certified':all(x['finite_root_gap_certified'] for x in cases.values()),'global_optimality_certified':False,'cases':cases}
 path=F/'CH40F_FULL_15_ACCEPTANCE.json';tmp=path.with_suffix('.tmp');tmp.write_text(json.dumps(out,indent=2,sort_keys=True)+'\n');tmp.replace(path)
 print('CH40F PASS all fifteen original 127-node producer/baseline/independent math checks',json.dumps(s), 'global: NO_GO',flush=True)
if __name__=='__main__':main()