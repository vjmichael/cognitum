"""Read-only CH33 source-bound, checkpoint, archive and benchmark consistency audit."""
import hashlib,json,sys
from pathlib import Path
D=Path(__file__).resolve().parent;R=D.parent;sys.path[:0]=[str(D)]
from compaction33 import _read_envelope,_read_archive,ARCHIVE_NAME
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()

def audit():
    p=D/'frozen_protocol.json'; frozen=json.loads(p.read_text())
    if sha(p)!=(D/'frozen_protocol.sha256').read_text().split()[0]:raise ValueError('CH33 protocol altered')
    if sha(R/'CH_C14_29/frozen_protocol.json')!=frozen['original_CH29_protocol_sha256']:
        raise ValueError('Original CH29 frozen protocol altered')
    if sha(R/'CH_C14_32/journal32.py')!=frozen['original_CH32_journal_implementation_sha256']:
        raise ValueError('CH32 original journal implementation altered')
    study=json.loads((D/'benchmark_results.json').read_text())
    chaos=json.loads((D/'chaos_results.json').read_text())
    if study['cases']!=15 or len(study['per_case'])!=15 or len(frozen['original_input_sha256'])!=15:
        raise ValueError('Missing original CH23 cases')
    if chaos['hard_process_terminations']!=5 or chaos['independent_cold_restart_and_full_history']['full_archived_history']['replayed_frames']!=6:
        raise ValueError('Hard termination or archive replay audit incomplete')
    expected=set(frozen['original_input_sha256']);actual=set()
    for row in study['per_case']:
        c=row['case_id'];actual.add(c)
        if row['original_case_sha256']!=frozen['original_input_sha256'][c]:raise ValueError('Wrong original CH23 data SHA')
        if row['CH32_external_original_head_sha256']!=frozen['original_CH32_journal_heads'][c]:raise ValueError('Wrong original CH32 head')
        sources=sorted((R/'CH_C14_32/journals'/c).glob('*.json'))
        if len(sources)!=6 or row['source_frames_sha256']!=[sha(p) for p in sources]:raise ValueError('CH32 source mismatch')
        cp=_read_envelope(D/'active'/c/'checkpoint.json')
        if cp['sha256']!=row['second_compaction']['checkpoint_sha256'] or cp['body']['head_sha256']!=frozen['original_CH32_journal_heads'][c]:
            raise ValueError('Compacted checkpoint external pin mismatch')
        if len(list((D/'active'/c).glob('[0-9]*.json')))!=0:
            raise ValueError('Uncompacted active journal records remain')
        archived=list((D/'archives'/c).glob('*.zlib'))
        if len(archived)!=2:
            raise ValueError('Expected two retained archive epochs')
        for item in archived:
            if not ARCHIVE_NAME.fullmatch(item.name):raise ValueError('Unknown archive format')
            _read_archive(item)
        final=row['cold_restart']
        if final['fresh_MPFR_bounds']!=127 or final['full_archived_history']['replayed_frames']!=6 or \
            not final['full_archived_history']['archived_history_reverified_with_MPFR']:
            raise ValueError('Independent source mathematical replay absent')
        if abs(final['checkpoint_gap']-row['original_CH29_127_gap'])>1e-10:
            raise ValueError('Compacted mathematical bound changed')
    if actual!=expected:raise ValueError('Original cohort case mismatch')
    if sum(r['historical_ambiguous'] for r in study['per_case'])!=3:raise ValueError('Ambiguity refusals changed')
    if study['global_optimality_certifications']!=0:raise ValueError('Invalid release promotion')
    return {'original_cases':len(actual),'original_CH32_frames':len(actual)*6,
            'archived_epochs':sum(len(list((D/'archives'/c).glob('*.zlib'))) for c in actual),
            'fresh_final_MPFR_replays':len(actual),'full_historical_MPFR_replays':len(actual),
            'hard_OS_exit_events':chaos['hard_process_terminations'],
            'historical_ambiguity_refusals':3,'global_certifications':0,
            'scientific_release':'NO_GO'}
if __name__=='__main__':print(json.dumps(audit(),indent=2,sort_keys=True))
