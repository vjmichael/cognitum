"""Seeded, independent arithmetic checks of C15 T2/T3 P2B research references.

This does NOT validate scene/sensor authenticity or compare original OctoMap.
Run: PYTHONPATH=. python tools/run_c15_t2_t3_p2b_study.py [output.json]
"""
import hashlib,json,math,random,sys
from pathlib import Path
from cognitum.proto import assembly_pb2 as a, ray_occupancy_pb2 as r
from cognitum.spatial_assembly import analyze
from cognitum.spatial_ray_occupancy import integrate

RNG_SEED=150203

def main():
    rng=random.Random(RNG_SEED)
    successes={'t2_cases':0,'t2_expected_present':0,'t2_explicit_absence':0,'t2_contradictions':0,'t2_unknown':0,'t3_cases':0,'t3_ray_cell_matches':0,'t3_log_odds_checks':0}
    for n in range(240):
        q=a.AssemblyResearchRequest(schema_version=1,graph_id=f'g{n}',conversation_id='study',research_only=True)
        for ident in ('assembly','part1','part2'):
            q.objects.add(id=ident,kind='generic',evidence=a.ASSEMBLY_OBSERVED,source_ref='synthetic')
        count=rng.randrange(3);is_absent=rng.choice((False,True));required=rng.randrange(1,3)
        for j in range(count):
            q.memberships.add(part_id=f'part{j+1}',assembly_id='assembly',role='supports',evidence=a.ASSEMBLY_OBSERVED,source_ref='synthetic')
        if is_absent:
            q.absences.add(assembly_id='assembly',role='supports',evidence=a.ASSEMBLY_OBSERVED,source_ref='synthetic')
        q.requirements.add(assembly_id='assembly',role='supports',minimum_count=required,source_ref='spec')
        status=analyze(q).roles[0].status
        oracle=(a.ASSEMBLY_CONTRADICTION if count and is_absent else a.ASSEMBLY_EXPLICIT_ABSENCE if is_absent else a.ASSEMBLY_PRESENT_CLAIM if count>=required else a.ASSEMBLY_NOT_ESTABLISHED)
        assert status==oracle,(n,count,is_absent,required,status,oracle)
        successes['t2_cases']+=1
        successes[{a.ASSEMBLY_PRESENT_CLAIM:'t2_expected_present',a.ASSEMBLY_EXPLICIT_ABSENCE:'t2_explicit_absence',a.ASSEMBLY_CONTRADICTION:'t2_contradictions',a.ASSEMBLY_NOT_ESTABLISHED:'t2_unknown'}[status]]+=1
    for n in range(240):
        q=r.RayBatch(schema_version=1,volume_id=f'v{n}',conversation_id='study',voxel_size_m=1,max_axis=8,research_only=True)
        start=tuple(rng.uniform(.12,7.88) for _ in range(3))
        end=tuple(rng.uniform(.12,7.88) for _ in range(3))
        hit=rng.choice((False,True))
        q.rays.add(start=r.Ray3(x=start[0],y=start[1],z=start[2]),end=r.Ray3(x=end[0],y=end[1],z=end[2]),endpoint_hit=hit,source_ref='simulated',tick=n+1,hit_probability=.75,free_probability=.3)
        result=integrate(q)
        sampled=[]
        for i in range(7001):
            t=i/7000
            xyz=tuple(int(math.floor(start[k]+(end[k]-start[k])*t)) for k in range(3))
            if not sampled or sampled[-1]!=xyz:sampled.append(xyz)
        got=sorted((c.x,c.y,c.z) for c in result.cells)
        assert got==sorted(sampled),(n,got,sampled)
        successes['t3_ray_cell_matches']+=1
        by_coord={(c.x,c.y,c.z):c for c in result.cells}
        for pos,xyz in enumerate(sampled):
            true_hit=hit and pos==len(sampled)-1
            cell=by_coord[xyz]
            expected=math.log(.75/.25) if true_hit else math.log(.3/.7)
            assert abs(cell.measured_log_odds-expected)<1e-12,(n,xyz)
            successes['t3_log_odds_checks']+=1
        successes['t3_cases']+=1
    report={'milestone':'C15 T2/T3 P2B','seed':RNG_SEED,'method':'independent synthetic count oracle + 7001-point numerical segment sampler; log-odds formula checked independently','results':successes,'limitations':['synthetic only','single-ray arithmetic; not calibrated sensor confidence','no authentic sensor, original OctoMap, or original OpenVDB integration','does not validate real-world functional performance or assembly engineering','no Lu actions or permissions']}
    raw=json.dumps(report,sort_keys=True,indent=2).encode()
    output=Path(sys.argv[1] if len(sys.argv)>1 else 'docs/components/spatial/P2B-reproducible-study.json')
    output.parent.mkdir(parents=True,exist_ok=True);output.write_bytes(raw+b'\n')
    print(json.dumps(successes,sort_keys=True))
    print('SHA256',hashlib.sha256(output.read_bytes()).hexdigest())

if __name__=='__main__':main()
