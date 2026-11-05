"""Record the original CH23/CH29/CH32 identity and CH33 engineering protocol."""
import hashlib,json
from pathlib import Path
D=Path(__file__).resolve().parent;R=D.parent
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
ch29=json.loads((R/'CH_C14_29/frozen_protocol.json').read_text())
ch32=json.loads((R/'CH_C14_32/heads.json').read_text())
assert set(ch29['original_case_sha256'])==set(ch32) and len(ch32)==15
out={'milestone':'CH-C14-33','date':'2026-11-02','status':'research_only',
'original_input_sha256':ch29['original_case_sha256'],
'original_CH32_journal_heads':ch32,
'original_CH29_protocol_sha256':sha(R/'CH_C14_29/frozen_protocol.json'),
'original_CH32_journal_implementation_sha256':sha(R/'CH_C14_32/journal32.py'),
'previous_verified_commit':'9d494ea1f110cc03f978e632955373ef06c26024',
'journal_compaction_schedule':[{'after_frame':3,'nodes':63},{'after_frame':5,'nodes':127}],
'archived_original_nodes':[7,15,31,63,95,127],
'original_case_count':15,'expected_ambiguity_refusals':3,
'MPFR_verified_precision_bits':224,'proof_gap_threshold':0.05,
'active_storage_budget_per_case_bytes':102400,
'baseline':'exact CH32 original frames; no synthetic data, no new solver runs',
'cold_recovery':'replay 127-node checkpoint from scratch with original data and externally pinned hashes',
'archival_audit':'replay all six source frames across two historical compressed epochs',
'hard_termination_events':['before_snapshot_rename','after_snapshot_fsync','during_prune','after_snapshot_rename','after_snapshot_fsync'],
'power_loss_tested':False,'Windows_platform_tested':False,
'full_archival_retention_required':True,
'archive_growth_is_unbounded_over_unlimited_history':True,
'actual_savepoint_integrity_requires_external_head_and_checkpoint_pin':True,
'production_release':'NO_GO'}
p=D/'frozen_protocol.json';p.write_text(json.dumps(out,sort_keys=True,indent=2)+'\n')
(D/'frozen_protocol.sha256').write_text(sha(p)+'  frozen_protocol.json\n')
print(sha(p))