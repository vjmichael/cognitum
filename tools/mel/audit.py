"""MEL-01 read-only inventory compiler. No runtime registration or permission.

The historical audit is a frozen evidence snapshot, not completed-function
inventory. The compiled catalog is engineering metadata, never a model tool list.
"""
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import subprocess
import os

BASE = '934fcda26ac54856675db50fd9e7fa4986424e9a'
DOCS = 'docs/research/mel/'
LEGACY = 'docs/research/COG03_HDC_RESEARCH_REGISTER.json'
DOC_HASHES = {
    'ARCHITECTURE.md': '6346d4f3b24856c389fa6a3bb47bab5130bf0839176b3b47d8418a9892790ad8',
    'RECONCILIATION.md': '2aa9487945de181edc16fa4b7296508cde37197abdc5589f433cf3e735f436e0',
    'MASTER_REGISTER.md': 'b916f2db752339d2a75a0802968b424603e9450918593d4422cff5f4435382ae',
}
BOUNDARY = ('cognitum/contracts.py','cognitum/registry.py','cognitum/runtime.py',
            'cognitum/policy.py','cognitum/worker.py','cognitum/cooperative.py',
            'cognitum/capability_route_proposal.py','cognitum/lu_ce_handoff.py')


def groups(prefix, first, last):
    return [f'{prefix}{i:02d}' if prefix in ('S','I-') else f'{prefix}{i}'
            for i in range(first,last+1)]


EXPECTED = set(groups('H',1,60)+groups('K',1,60)+groups('S',1,24)+groups('I-',1,20))
LEGACY_IDS = {f'{p}{i:02d}' for p,n in [('V',16),('E',13),('M',7),('R',9),('L',28),('H',12)] for i in range(1,n+1)}

# Track references are evidence navigation, NOT proof that every group in a
# track has the corresponding native capability. Open/adjacent groups remain so.
TRACKS = (
 ('COG-03-ALGEBRA','H',1,11,'hdc_algebra hdc_survey_algebra hdc_ghrr hdc_capacity hdc_frontier_encoders'),
 ('COG-03-MEMORY','H',12,19,'hdc_encoders hdc_structured_encoders hdc_associative hdc_associative_lifecycle hdc_memory_advanced hdc_canonical'),
 ('COG-03-VFA','H',20,24,'vfa_random vfa_periodic vfa_rkhs vfa_multivariate'),
 ('COG-03-ARITHMETIC','H',25,27,'hdc_algebra hdc_hardware hdc_encoders'),
 ('COG-03-FACTORIZATION','H',28,37,'hdc_resonator_frontier hdc_reasoning_advanced hdc_uncertain_visual hdc_visual_closeout'),
 ('COG-03-SPATIAL','H',38,40,'hdc_dynamic_spatial vfa_multivariate'),
 ('COG-03-REASONING','H',41,45,'hdc_reasoning_advanced hdc_resonator_frontier hdc_canonical'),
 ('COG-03-EXECUTABLE','H',46,49,'hdc_structured_encoders hdc_reasoning_advanced hdc_temporal'),
 ('COG-03-LEARNING','H',50,55,'hdc_learning hdc_advanced_learning hdc_frontier_learning hdc_learning_closeout hdc_stream_discovery hdc_cooperative_learning'),
 ('COG-03-EXTENDED','H',56,60,'hdc_temporal hdc_temporal_closeout hdc_cooperative_learning hdc_dynamic_spatial'),
 ('COG-04-FOUNDATIONS','K',1,17,'kan_portable kan_optional kan_approval'),
 ('COG-04-ARCHITECTURES','K',18,23,'kan_portable kan_optional'),
 ('COG-04-LEARNING','K',24,28,'kan_portable'),
 ('COG-04-GEOMETRY','K',29,34,''),
 ('COG-04-OPERATORS','K',35,39,''),
 ('COG-04-SCIENCE','K',40,45,'kan_portable'),
 ('COG-04-DYNAMICS','K',46,50,'kan_portable'),
 ('COG-04-SYMBOLIC','K',51,54,''),
 ('COG-04-ADAPTATION','K',55,60,''),
 ('COG-MATH-S','S',1,24,''),
 ('COG-MATH-I','I-',1,20,'vfa_multivariate kan_portable hdc_canonical'),
)
SHARED = ('cognitum/scientific_math.py','cognitum/exact_reference.py',
          'cognitum/formal_backend.py','cognitum/formal_solver.py','cognitum/probability_backend.py',
          'cognitum/causal_specialists.py','cognitum/optimization.py','cognitum/planning_graph.py',
          'cognitum/physics_ode.py','cognitum/spatial_geometry.py','cognitum/topology_gudhi.py',
          'cognitum/temporal_statespace.py')
HISTORICAL = ('docs/quality/P22_KAN_Real_Physics_Training_20261101.md',
              'docs/quality/P22b_KAN_Wind_Drag_Lag_Training_20261101.md')

# Old register H01-H12 mean hardware, NOT the master H1-H12 definitions.
# Cross-links are scope/accounting relationships, not acceptance claims.
LINKS = '''V01 H1 H2 H7 H11;V02 H1 H2 H11;V03 H1 H8 H11;V04 H1 H8 H11
V05 H1 H7 H11;V06 H1 H2 H11;V07 H1 H2 H11 H26;V08 H1 H10 H11
V09 H1 H10 H11;V10 H1 H10 H11;V11 H1 H7 H11;V12 H1 H7 H11
V13 H1 H10 H11;V14 H1 H2 H10;V15 H1 H3 H27;V16 H1 H4 H6 H7
E01 H5 H12;E02 H12;E03 H9 H11 H12 H51;E04 H5 H12;E05 H12 H13 H56 H57
E06 H13 H14 H15 H46 H47 H56;E07 H4 H5 H9 H12;E08 H3 H4 H12
E09 H9 H12 H51;E10 H12 H18;E11 H20 H21 H38;E12 H12 H51 H52;E13 H7 H12 H26
M01 H16 H19;M02 H16 H17;M03 H16 H17;M04 H16 H29 H58;M05 H16 H18
M06 H6 H7 H16;M07 H13 H15 H19 H43
R01 H28 H30;R02 H28 H29 H30 H31 H32;R03 H15 H41;R04 H41 H42
R05 H32 H43 H44 H48;R06 H41 H60;R07 H28 H29 H58;R08 H42 H43 H45;R09 H43 H57 H60
L01 H50;L02 H50 H52;L03 H50 H52 H53;L04 H50 H52;L05 H50 H51
L06 H50 H51;L07 H6 H50 H51;L08 H7 H50 H51;L09 H26 H50;L10 H50 H51
L11 H50 H51;L12 H51 H52 H53;L13 H51;L14 H8 H51;L15 H50 H51
L16 H4 H7 H51;L17 H21 H27 H54;L18 H50 H54;L19 H53 H54;L20 H53 H54
L21 H54;L22 H54 H57;L23 H33 H53 H57;L24 H56;L25 H56 H58
L26 H55 H60;L27 H53 H59;L28 H50 H54 H59
H01 H11 H27 S23 I-19;H02 H27 H50 S23 I-19;H03 H27 S23 I-19;H04 H1 H10 I-19
H05 H27 H59 S23 I-19;H06 H51 H57 S23;H07 H26 H27 S23 I-19;H08 H27 I-19
H09 H19 H59 I-19;H10 H32 H44 I-19;H11 H51 H55 I-19;H12 H27 S23 I-19'''

# Development identifiers only, never passed to Registry.resolve or to Lu.
OPERATIONS = (
 ('vfa.evaluate','MEL-02','H20 H21 S09','vfa_rkhs vfa_multivariate','bounded function plus finite coordinates -> values'),
 ('vfa.gradient','MEL-02','H23 S16','vfa_multivariate','bounded function plus coordinates -> gradient with declared derivative semantics'),
 ('hdc.bind','MEL-03','H1 H11 H15','hdc_algebra','compatible VSA specification and operands -> bound representation'),
 ('hdc.query','MEL-03','H16 H19 H41','hdc_optional hdc_canonical','revision-bound query -> candidates, canonical witnesses separately'),
 ('kan.evaluate','MEL-03','K1 K11 K12 K18','kan_optional kan_approval kan_portable','approved checkpoint and domain-qualified inputs -> approximate values'),
 ('vfa.compose','MEL-04','H23 H24','vfa_multivariate','compatible functions -> typed expression, not implied closure'),
 ('convert.kan_to_vfa','MEL-04','I-01 I-03 I-14','kan_portable vfa_rkhs','bounded function conversion; held-out error qualification required'),
 ('convert.vfa_to_kan','MEL-04','I-02 I-03 I-14','vfa_rkhs kan_portable','blocked on trainable KAN; no implementation yet'),
 ('kan.fit','COG-04','K11 K24 K25 K28','kan_portable','blocked on recovered or reconstructed trainable implementation'),
 ('verify.function_equivalence','MEL-05','I-14 K54 S18','vfa_rkhs vfa_multivariate','domain-qualified independent comparisons, not automatic symbolic proof'),
 ('formal.check_constraint','MEL-04','I-18 S18 S19','', 'reuse independently checked formal semantics; bridge not yet admitted'),
)


def require(condition, message):
    if not condition:
        raise ValueError(message)


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def source_paths():
    names = {n for _,_,_,_,s in TRACKS for n in s.split()}
    names.update(n for _,_,_,s,_ in OPERATIONS for n in s.split())
    return set(BOUNDARY+SHARED+HISTORICAL) | {f'cognitum/research/{n}.py' for n in names}


def legacy_links():
    result = {}
    for line in re.split(r'[;\n]',LINKS):
        if not line.strip():
            continue
        key,*values = line.split()
        require(key not in result and len(values)==len(set(values)) and set(values)<=EXPECTED,'invalid legacy link')
        result[key] = values
    require(set(result)==LEGACY_IDS,'legacy crosswalk mismatch')
    return result


def original_ids(master):
    hk = re.findall(r'^## ([HK]\d+)\.|^\| \*\*([HK]\d+) —',master,re.M)
    ids = [a or b for a,b in hk]
    instruments = master.split('# Part III — Shared mathematical investigation infrastructure',1)[1].split('# Part IV',1)[0]
    shared = [l.split('|')[1].strip() for l in instruments.splitlines() if l.startswith('| ') and not l.startswith('| Instrument ')]
    require(len(shared)==24,'shared instrument count')
    ids += groups('S',1,len(shared))
    ids += re.findall(r'^\| (I-\d{2}) \|',master,re.M)
    require(len(ids)==164 and set(ids)==EXPECTED,'master inventory mismatch')
    return shared


def compile_inventory(master, reconciliation, legacy, baseline):
    shared = original_ids(master)
    links = legacy_links()
    old_ids = [e['id'] for e in legacy['entries']]
    require(len(old_ids)==85 and set(old_ids)==LEGACY_IDS,'original 85 entries missing or duplicated')
    require({e['id']:e['method'] for e in legacy['entries']}==baseline['legacy_identities'],'legacy method identity drift')
    require(baseline['baseline_sha']==BASE and baseline['native_run']==44443339840,'baseline identity')
    blobs = baseline['source_git_blobs']
    require(set(blobs)==source_paths() and all(re.fullmatch('[0-9a-f]{40}',v) for v in blobs.values()),'source inventory mismatch')
    tracks = {}
    for owner,prefix,start,end,modules in TRACKS:
        refs = [f'cognitum/research/{n}.py' for n in modules.split()]
        if prefix=='S' or prefix=='I-':refs+=list(SHARED)
        if prefix=='K':refs+=list(HISTORICAL)
        for key in groups(prefix,start,end):
            require(key not in tracks,'duplicate workstream assignment')
            tracks[key]=(owner,refs)
    require(set(tracks)==EXPECTED,'missing track assignment')
    rows = {}
    for line in reconciliation.splitlines():
        if not re.match(r'^\| (?:[HK]\d+|S\d{2}|I-\d{2}) \|',line):continue
        key,title,status,evidence,residual = [x.strip() for x in line.strip().strip('|').split('|')]
        require(key in EXPECTED and key not in rows and status in ('B','P','A','O') and all((title,evidence,residual)),'invalid reconciliation row')
        if key.startswith('S'):require(title==shared[int(key[1:])-1],'shared instrument identity mismatch')
        owner,refs = tracks[key]
        rows[key] = dict(id=key,title=title,coverage=status,evidence=evidence,remaining=residual,owner=owner,
                         navigation_refs=refs,legacy_scope_links=[k for k,v in links.items() if key in v],
                         mel_admission='not_admitted',production_enabled=False)
    require(set(rows)==EXPECTED,'incomplete reconciliation')
    ops=[]
    for name,stage,ids,modules,contract in OPERATIONS:
        require(set(ids.split())<=EXPECTED,'invalid operation references')
        refs=[f'cognitum/research/{n}.py' for n in modules.split()]
        if name=='formal.check_constraint':refs=['cognitum/formal_solver.py','cognitum/formal_backend.py']
        ops.append(dict(operation=name,stage=stage,groups=ids.split(),navigation_refs=refs,contract_sketch=contract,
                        executable=False,model_advertised=False,descriptor_status='reserved_not_routable'))
    require(len({o['operation'] for o in ops})==len(ops),'duplicate reserved operation')
    return dict(schema='cognitum.mel.inventory.v1',baseline_sha=BASE,native_run=44443339840,
                scope='engineering_inventory_only_not_dispatch',groups=list(rows.values()),
                legacy_links=links,reserved_operations=ops,source_git_blobs=blobs,
                counts={p:dict(Counter(v['coverage'] for k,v in rows.items() if k.startswith(p))) for p in ('H','K','S','I-')},
                mel_admission=False,production_enabled=False)


def read_documents(root):
    out={}
    for name,expected in DOC_HASHES.items():
        raw=(root/DOCS/name).read_bytes()
        require(digest(raw)==expected,'frozen document drift '+name)
        out[name]=raw.decode('utf8')
    return out


def git(root,*args):
    return subprocess.check_output(['git',*args],cwd=root,text=True).strip()


def main():
    root=Path(__file__).resolve().parents[2]
    expected=os.getenv('COG03BC_EXPECTED_SHA')
    head=git(root,'rev-parse','HEAD')
    require(os.getenv('GITHUB_ACTIONS')!='true' or bool(expected),'missing hosted SHA')
    require(not expected or head==expected,'wrong checkout')
    docs=read_documents(root)
    legacy=json.loads((root/LEGACY).read_text(encoding='utf8'))
    baseline=json.loads((root/DOCS/'BASELINE.json').read_text(encoding='utf8'))
    inventory=compile_inventory(docs['MASTER_REGISTER.md'],docs['RECONCILIATION.md'],legacy,baseline)
    # Preserve original IDs/methods, but allow their evidence/status to evolve.
    inventory['legacy_register_changed_since_baseline']=(git(root,'rev-parse','HEAD:'+LEGACY)!=baseline['legacy_register_blob'])
    current={p:git(root,'rev-parse','HEAD:'+p) for p in sorted(source_paths())}
    for p in BOUNDARY:
        require(current[p]==baseline['source_git_blobs'][p],'runtime boundary drift requires MEL review '+p)
    inventory['current_source_sha']=head
    inventory['changed_navigation_sources']=[p for p,v in current.items() if v!=baseline['source_git_blobs'][p]]
    out=root/'cog03bc-artifacts'/'mel01';out.mkdir(parents=True,exist_ok=True)
    (out/'inventory.json').write_text(json.dumps(inventory,indent=2,ensure_ascii=False)+'\n',encoding='utf8')
    print('MEL-01: 164 master groups, 85 preserved legacy entries,',len(inventory['reserved_operations']),'reserved non-routable operations; no admission')


if __name__=='__main__':main()
