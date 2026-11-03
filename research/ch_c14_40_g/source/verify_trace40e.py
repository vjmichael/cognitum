"""CH40-E independent read-only verifier for real CH29 MPFR producer traces.

NO imports of the source MPFR solver, coupled27.py, or CH40-D *producer*.
Exact dyadic interval arithmetic checks the emitted producer's operations;
independent rational / Decimal enclosures recompute exp/log/p/slope.

These tests validate selected COUPLED_TANGENT producer caps; the direct
Firth/Loewner formula is not yet fully traced and must remain untrusted.
"""
from __future__ import annotations
import argparse,hashlib,json,pathlib,sys,zipfile
from fractions import Fraction as F
from decimal import Decimal,Context,localcontext,ROUND_FLOOR
ROOT=pathlib.Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT if (ROOT/'rational_kernel40d.py').is_file() else ROOT.parent/'CH_C14_40_D'))
from rational_kernel40d import R,eta,p_of,det,weight_of,model_of,point_objective
PIN='9e713b102982ea09fecbcfbd27bccf55d56808188bfc3e5be1ba76922000ae6b'

class Refusal(ValueError):pass

def canonical(x):return json.dumps(x,sort_keys=True,separators=(',',':'),allow_nan=False)
def sha(b):return hashlib.sha256(b).hexdigest()

def dyad(d):
 if type(d) is not dict or set(d)!={'significand','exponent'}:raise Refusal('Malformed MPFR dyad')
 s=d['significand'];e=d['exponent']
 if type(s) is not str or not s or len(s)>4096 or type(e) is not int or abs(e)>10000:raise Refusal('Out-of-range MPFR dyad')
 sign=-1 if s.startswith('-') else 1
 bits=s.lstrip('-')
 if not bits or any(z not in '01' for z in bits):raise Refusal('Invalid MPFR significand')
 sh=e-len(bits)
 return F(sign*int(bits,2)*2**max(sh,0),2**max(-sh,0))

def interval(ends):
 if type(ends) is not list or len(ends)!=2:raise Refusal('Wrong interval endpoint count')
 x,y=map(dyad,ends)
 if x>y:raise Refusal('Inverted MPFR interval')
 return R.raw(x,y)

def enclosed(actual,outer,label):
 if not outer.contains(actual):raise Refusal(f'Producer interval excludes independent mathematics: {label}')

def upper(rec):return dyad(rec['effective_cap'])

def verify_dual(cert,node,dual,source_box):
 qidx=dual.get('q_index');qs=cert['dual_matrices']
 if type(qidx)is not int or not 0<=qidx<len(qs):raise Refusal('Invalid dual index')
 Q=[[F(str(z)) for z in row] for row in qs[qidx]]
 d=cert['model']['d'];rows=cert['model']['rows']
 if len(Q)!=d or any(len(row)!=d for row in Q) or any(Q[i][j]!=Q[j][i] for i in range(d) for j in range(d)):
  raise Refusal('Dual not symmetric')
 if Q[0][0]<=0 or (d>=2 and det([row[:2] for row in Q[:2]])<=0) or (d==3 and det(Q)<=0):raise Refusal('Dual matrix not SPD')
 if len(dual['rows'])!=len(rows) or len(dual['kappa'])!=len(rows):raise Refusal('Incomplete producer tangent rows')
 const=interval(dual['constant'])
 try: expected=-R(F(1,2))*R(det(Q)).ln()-R(F(d,2))
 except Exception as exc:raise Refusal('Independent dual constant unavailable') from exc
 enclosed(expected,const,'dual logdet constant')
 sumbound=const.hi
 for j,(r,raw,kraw) in enumerate(zip(rows,dual['rows'],dual['kappa'])):
  xi=[F(str(x)) for x in r['x']];n,s=r['n'],r['s']
  p0=F(str(raw['p0_decimal']))
  if not 0<p0<1:raise Refusal('Tangent support outside (0,1)')
  ip0=interval(raw['p0']);enclosed(R(p0),ip0,'tangent location')
  k=dyad(kraw);lever=sum((xi[a]*Q[a][b]*xi[b] for a in range(d) for b in range(d)),F(0))
  if lever<=0 or k<F(n,2)*lever:raise Refusal('MPFR dual Fisher leverage underbound')
  ko=interval(raw['k']);enclosed(R(k),ko,'kappa MPFR interval')
  pp=p_of(eta(xi,source_box));recorded_p=interval(raw['p_box']);enclosed(pp,recorded_p,'logistic probability')
  val=R(s)*R(p0).ln()+R(n-s)*R(1-p0).ln()+R(k*p0*(1-p0))
  slope=R(F(s,1)/p0-F(n-s,1)/(1-p0)+k*(1-2*p0))
  valrec=interval(raw['g_value']);sloperec=interval(raw['g_slope']);caprec=interval(raw['line_cap'])
  enclosed(val,valrec,'tangent value');enclosed(slope,sloperec,'tangent slope')
  # Reconstruct exact rational enclosure from the FULL producer MPFR inputs,
  # not just fresh high-precision approximate evaluation.
  reconstructed=valrec+sloperec*(recorded_p-ip0)
  enclosed(reconstructed,caprec,'MPFR tangent interval arithmetic')
  if caprec.hi < val.hi + (slope*(pp-R(p0))).hi:raise Refusal('Tangent cap excludes independent majorant')
  sumbound+=caprec.hi
 if dyad(dual['computed_total_hi'])<sumbound:raise Refusal('MPFR accumulated upper rounded inward')
 return dyad(dual['computed_total_hi'])


def verify_direct(cert,trace,node):
    """Independently replay producer's Loewner/entropy/Gram MPFR local cap.

    Every numerical assertion must be a certified outward interval. A narrower
    recorded upper than the reconstructed exact source operation is refused.
    """
    if type(trace) is not dict:raise Refusal('Missing complete producer direct witness')
    d,rows,xs,(basis_ids,minor)=model_of(cert)
    if len(trace.get('rows',[]))!=len(rows):raise Refusal('Missing direct Fisher rows')
    box=[[F(str(a)),F(str(b))] for a,b in node['box']]
    ll=R(0);scalar_cap_uppers=F(0);stored_w=[]
    for i,(row,x,record) in enumerate(zip(rows,xs,trace['rows'])):
        n,s=row['n'],row['s'];ze=eta(x,box);p=p_of(ze);w=weight_of(ze)
        zet=interval(record['eta']);wp=interval(record['p']);ww=interval(record['w']);cap=interval(record['binomial_cap'])
        enclosed(ze,zet,'direct eta')
        enclosed(p,wp,'direct logistic probability')
        enclosed(w,ww,'direct Fisher weight')
        # Verify scalar max of concave binomial log likelihood, including the
        # monotone s=0 or s=n boundary cases.
        if s==0:
            individual=-R(n)*(R(1)+R(zet.lo).exp()).ln()
        elif s==n:
            individual=R(n)*R(zet.hi)-R(n)*(R(1)+R(zet.hi).exp()).ln()
        else:
            a=F(s,n);individual=R(s)*R(a).ln()+R(n-s)*R(1-a).ln()
        if cap.hi<individual.hi:raise Refusal('Unsafe direct scalar likelihood cap')
        scalar_cap_uppers+=cap.hi
        ll=ll+R(s)*zet-(R(1)+zet.exp()).ln()*R(n)
        stored_w.append(ww)
    llrecord=interval(trace['ll']);enclosed(ll,llrecord,'direct loglikelihood sum')
    ll_cap_record=interval(trace['ll_cap'])
    if ll_cap_record.hi<scalar_cap_uppers:raise Refusal('Inward-rounded sum of per-row scalar maxima')
    fm=[[R(0) for _ in range(d)] for _ in range(d)]
    um=[[R(0) for _ in range(d)] for _ in range(d)]
    for row,x,weight in zip(rows,xs,stored_w):
        for j in range(d):
            for k in range(d):
                c=F(row['n'])*x[j]*x[k]
                fm[j][k]=fm[j][k]+R(c)*weight
                um[j][k]=um[j][k]+R(c)*R(weight.hi)
    Fraw=[[interval(t) for t in row] for row in trace['F']]
    Uraw=[[interval(t) for t in row] for row in trace['U']]
    if len(Fraw)!=d or len(Uraw)!=d or any(len(row)!=d for row in Fraw+Uraw):raise Refusal('Wrong Fisher matrix shape')
    for j in range(d):
        for k in range(d):
            enclosed(fm[j][k],Fraw[j][k], 'Fisher interval matrix')
            enclosed(um[j][k],Uraw[j][k], 'Fisher upper Gram matrix')
    detF=interval(trace['detF']);detU=interval(trace['detU']);had=interval(trace['had'])
    enclosed(det(Fraw),detF,'interval determinant of Fisher')
    enclosed(det(Uraw),detU,'upper Gram determinant')
    independent_had=R(1)
    for j in range(d):independent_had=independent_had*Fraw[j][j]
    enclosed(independent_had,had,'Hadamard bound')
    # A full-rank design minor and strictly positive weights provide a valid
    # Fisher determinant LOWER bound by the Cauchy-Binet expansion.
    ref=minor*minor
    for i in basis_ids:ref*=rows[i]['n']*stored_w[i].lo
    if ref<=0:raise Refusal('No independent positive Fisher minor')
    det_record=interval(trace['det_enclosure'])
    if det_record.lo>max(ref,detF.lo):raise Refusal('Fisher lower bound exceeds proved lower')
    if det_record.hi!=min(detF.hi,had.hi,detU.hi):raise Refusal('Fisher upper not from reported min rules')
    if det_record.lo<=0:raise Refusal('Nonpositive Fisher log domain')
    logdet=interval(trace['logdet']);enclosed(det_record.ln(),logdet,'MPFR log determinant')
    # Validate original global likelihood tangent(s) from exact support beta.
    tangent_ceils=[]
    for anchor in trace['tangent_anchors']:
        point=[F(str(v)) for v in anchor['coords']]
        if len(point)!=d:raise Refusal('Wrong tangent dimension')
        f0=R(0);grad=[R(0) for _ in range(d)]
        for row,x in zip(rows,xs):
            zz=eta(x,[[v,v] for v in point]);pp=p_of(zz)
            f0=f0+R(row['s'])*zz-R(row['n'])*(R(1)+zz.exp()).ln()
            for j in range(d):grad[j]=grad[j]+(R(row['s'])-R(row['n'])*pp)*R(x[j])
        v=interval(anchor['value']);grads=[interval(g) for g in anchor['grad']]
        if len(grads)!=d:raise Refusal('Missing tangent components')
        enclosed(f0,v,'global loglikelihood tangent value')
        for j in range(d):enclosed(grad[j],grads[j],'global score anchor')
        tang=v
        for j in range(d):tang=tang+grads[j]*(R(*box[j])-R(point[j]))
        tangent_ceils.append(tang.hi)
    tang_record=trace['tangent_cap']
    if tangent_ceils:
        if tang_record is None or dyad(tang_record)<min(tangent_ceils):raise Refusal('Tangent cap below reconstructed upper')
    elif tang_record is not None:raise Refusal('Unexpected tangent without anchor')
    ll_upper=min([llrecord.hi,ll_cap_record.hi]+([dyad(tang_record)] if tang_record is not None else []))
    if dyad(trace['ll_upper'])!=ll_upper:raise Refusal('Likelihood upper not derived from recorded proof caps')
    bound=ll_upper+F(1,2)*logdet.hi
    direct=interval(trace['full'])
    if direct.hi<bound:raise Refusal('Original MPFR direct objective cap rounded inward')
    return direct


def validate_original_model_and_partition(cert,inp,proto):
    """Exact rational proof-tree geometry. Never trust signed parent IDs alone."""
    if type(cert.get('nodes')) is not list or not 1<=len(cert['nodes'])<=127:raise Refusal('Invalid original proof node count')
    if cert.get('claim_scope')!='finite_root_box_global_max_only' or cert.get('production_release')!='NO_GO':
        raise Refusal('Unauthorized original certificate scope')
    if len(cert['root_box'])!=len(inp['bounds']) or any(
        [F(str(a)),F(str(b))]!=[F(str(c)),F(str(d))]
        for (a,b),(c,d) in zip(cert['root_box'],inp['bounds'])
    ):raise Refusal('Root domain not the frozen original')
    # Original model consists of exact aggregations of original binary outcomes.
    raw={}
    for r in inp['rows']:
        key=tuple(F(str(x)) for x in r['x'])
        if r['y'] not in (0,1) or type(r['y']) is not int:raise Refusal('Invalid original outcome')
        n,s=raw.get(key,(0,0));raw[key]=(n+1,s+r['y'])
    groups={}
    for r in cert['model']['rows']:
        key=tuple(F(str(x)) for x in r['x'])
        if key in groups:raise Refusal('Duplicate model group')
        groups[key]=(r['n'],r['s'])
    if groups!=raw or cert['model']['n_raw']!=len(inp['rows']):raise Refusal('Original model grouping differs')
    if len(cert['incumbent'])!=cert['model']['d'] or any(
        not F(str(lo))<=F(str(x))<=F(str(hi))
        for x,(lo,hi) in zip(cert['incumbent'],inp['bounds'])
    ):raise Refusal('Infeasible original incumbent')
    nodes=cert['nodes'];seen=set()
    def walk(index,expected,parent,depth):
        if type(index)is not int or not 0<=index<len(nodes) or index in seen:raise Refusal('Proof tree cycle/orphan')
        seen.add(index);n=nodes[index]
        if n['id']!=index or n['parent_id']!=parent or n['depth']!=depth:raise Refusal('Incorrect parent/depth')
        if len(n['box'])!=len(expected) or any(
          [F(str(a)),F(str(b))]!=[F(str(c)),F(str(d))]
          for (a,b),(c,d) in zip(n['box'],expected)
        ):raise Refusal('Tree domain changed')
        if n.get('newton') or n['effective_box']!=n['box']:raise Refusal('Uncertified historical Newton action')
        if 'children' in n:
            kids=n['children'];axis=n['split_dim']
            if type(axis)is not int or not 0<=axis<len(expected) or len(kids)!=2 or kids[0]==kids[1]:
                raise Refusal('Invalid child rule')
            middle=(F(str(expected[axis][0]))+F(str(expected[axis][1])))/2
            if not F(str(expected[axis][0]))<middle<F(str(expected[axis][1])):raise Refusal('Invalid midpoint')
            left=[list(v) for v in expected];right=[list(v) for v in expected]
            left[axis][1]=middle;right[axis][0]=middle
            walk(kids[0],left,index,depth+1);walk(kids[1],right,index,depth+1)
    walk(0,[[F(str(a)),F(str(b))] for a,b in inp['bounds']],None,0)
    if len(seen)!=len(nodes):raise Refusal('Orphan nodes not covered')
    if sum('children' not in n for n in nodes)!=cert['leaf_count']:raise Refusal('Reported leaf count differs')
    return True

def verify(result, original_archive, *, progress=False):
 if sha(original_archive.read_bytes())!=PIN or result['original_archive_sha256']!=PIN:raise Refusal('Wrong external trust root')
 case=result['case'];cert=result['certificate']
 if cert.get('research_case_id')!=case or len(cert['nodes'])!=result['node_count'] or len(result['nodes'])!=result['node_count']:
  raise Refusal('Wrong case or missing nodes')
 with zipfile.ZipFile(original_archive) as z:
  proto=json.loads(z.read('CH_C14_29/frozen_protocol.json'))
  path='CH_C14_25/inputs/'+case+'.json'
  if sha(z.read(path))!=proto['original_case_sha256'].get(case) or result['original_case_sha256']!=proto['original_case_sha256'][case]:raise Refusal('Wrong original case pins')
  if sha(z.read('CH_C14_27/frozen_duals.json'))!=proto['original_dual_sha256']:raise Refusal('Wrong original dual pins')
  src_duals=json.loads(z.read('CH_C14_27/frozen_duals.json'))[case]
  if cert['dual_matrices']!=src_duals:raise Refusal('Producer dual matrices changed')
  if cert['model_sha256']!=sha(canonical(cert['model']).encode()):raise Refusal('Producer model changed')
  inp=json.loads(z.read(path))
  validate_original_model_and_partition(cert,inp,proto)
  if cert['original_data_identity']!=inp['original_CH23_identity']:raise Refusal('Case model identity changed')
  if cert['precision_bits']!=proto['precision_bits']:raise Refusal('Producer precision altered')
 if result['certificate_sha256']!=sha(canonical(cert).encode()):raise Refusal('Producer certificate hash changed')
 if result.get('scientific_release')!='NO_GO' or result.get('optimized_cap_independently_certified') is not False:raise Refusal('Premature scientific promotion')
 count={'nodes':0,'coupled_certified':0,'direct_certified':0,'inherited_caps_certified':0,'untrusted_caps':0,'coupled_candidates_checked':0}
 status={}
 for node,tr in zip(cert['nodes'],result['nodes']):
  idx=node['id'];count['nodes']+=1
  if progress and idx%8==0:print('Independent MPFR node',idx+1,'of',len(cert['nodes']),flush=True)
  if idx!=tr['id'] or node['parent_id']!=tr['parent'] or node['effective_box']!=tr['box'] or node['bound_mode']!=tr['mode'] or node['upper_method']!=tr['method']:
   raise Refusal('Inconsistent producer source node')
  if node.get('newton') or node['effective_box']!=node['box']:raise Refusal('Unverified Newton contraction/exclusion')
  direct=interval(tr['direct']); local=interval(tr['local']); cap=upper(tr)
  if tr['parent'] is None:
   if tr['parent_cap'] is not None or cap!=local.hi:raise Refusal('Wrong root MPFR cap')
  else:
   par=tr['parent']
   if par not in status or tr['parent_cap'] is None or dyad(tr['parent_cap'])!=status[par][0] or cap!=min(local.hi,status[par][0]):
    raise Refusal('Wrong parent-bound inheritance')
  if node['local_upper_bound_display']!=tr['display_local'] or node['upper_bound_ceil_display']!=tr['display_effective']:
   raise Refusal('Altered producer displays')
  checked_direct=verify_direct(cert,tr.get('direct_trace'),node)
  if checked_direct.lo!=direct.lo or checked_direct.hi!=direct.hi:raise Refusal('Original direct interval does not match producer trace')
  coupling=[]
  for dual in tr['dual_candidates']:
   val=verify_dual(cert,node,dual,[[F(str(a)),F(str(b))] for a,b in tr['box']]);coupling.append(val)
  count['coupled_candidates_checked']+=len(coupling)
  if (tr['mode']=='coupled') != bool(coupling):raise Refusal('Missing or extra coupled witnesses')
  this_certified=False
  if tr['method']=='coupled_logdet_dual':
   if not coupling or local.hi!=min(coupling) or local.hi>direct.hi:raise Refusal('Selected MPFR coupled minimum changed')
   this_certified=True;count['coupled_certified']+=1
  elif tr['method']=='direct':
   if local.hi!=direct.hi:raise Refusal('Direct selected upper differs')
   this_certified=True;count['direct_certified']+=1
  else:raise Refusal('Unknown producer method')
  parent_cert=bool(status[tr['parent']][1]) if tr['parent'] is not None else False
  if this_certified or (parent_cert and cap==status[tr['parent']][0]):
   count['inherited_caps_certified']+=1; certified=True
  else:
   count['untrusted_caps']+=1;certified=False
  status[idx]=(cap,certified)
 # Source truth: the certified cap on every terminal box bounds the finite
 # root. One independently evaluated feasible objective provides a LOWER bound.
 lower=point_objective(cert,[F(str(z)) for z in cert['incumbent']]).lo
 leaves=[n['id'] for n in cert['nodes'] if 'children' not in n]
 if not leaves or any(not status[i][1] for i in leaves):raise Refusal('Uncertified finite-root leaf cap')
 finite_ceiling=max(status[i][0] for i in leaves)
 tol=F(str(cert['tolerance']))
 finite_gap=finite_ceiling<=lower+tol
 with localcontext(Context(prec=90,rounding=ROUND_FLOOR)):
     lower_decimal=str(Decimal(lower.numerator)/Decimal(lower.denominator))
 if finite_gap and cert.get('status')=='UNRESOLVED_REFUSE_CERTIFICATION':
     # The original MPFR 160-bit run may have a looser incumbent lower, but
     # an independent finite-box proof can still report the stronger result
     # without promoting unrestricted scientific global optimality.
     pass
 return {'protocol':'CH40E-INDEPENDENT-MPFR-TANGENT-TRACE-VERIFY-V1','case':case,'checks':count,
         'all_source_geometry_consistent':True,
         'finite_root_independent_lower_outward90':lower_decimal,
         'finite_root_gap_certified':finite_gap,
         'finite_root_gap_certificate_scope':'PINNED_FINITE_ROOT_DOMAIN_ONLY',
         'all_recorded_selected_caps_certified':count['untrusted_caps']==0,
         'certification_scope':'ORIGINAL_DIRECT_LOEWNER_AND_COUPLED_TANGENT_MPFR_CAPS_SOURCE_TRACED',
         'producer_direct_formula_trace_complete':True,
         'producer_taylor_newton_trace_complete':False,
         'full_producer_proof_certified':False,
         'global_optimality_certified':False,
         'scientific_release':'NO_GO'}

def main():
 p=argparse.ArgumentParser();p.add_argument('--trace',type=pathlib.Path,required=True);p.add_argument('--archive',type=pathlib.Path,required=True);p.add_argument('--output',type=pathlib.Path);p.add_argument('--progress',action='store_true');a=p.parse_args()
 got=verify(json.loads(a.trace.read_text()),a.archive,progress=a.progress)
 if a.output:a.output.write_text(json.dumps(got,indent=2)+'\n')
 print(json.dumps(got,indent=2))
if __name__=='__main__':main()
