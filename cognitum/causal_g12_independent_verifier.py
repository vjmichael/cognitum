"""G12 independent arithmetic verifier for aggregate counts only.

Does not import the study generator, G7, G8, G9, G10 or G11. Cannot prove
that a causal graph or source data are authentic. Validates fixed design,
case totals, oracle math, computed statistics and summary aggregation.
"""
from collections import defaultdict
from math import isclose, fsum, isfinite

EXPECTED = {
 'CLEAN_INTERACTION':.23,
 'HIDDEN_COMMON_CAUSE':.02,
 'MISMEASURED_CONFOUNDER':.05,
 'SELECTION_COLLIDER':.15,
 'TRANSPORT_SHIFT':.39,
 'NEGATIVE_CONTROL':0.0}
ALLOWED_N=(300,900)
ALLOWED_SEEDS=tuple(range(73001,73081))


def independent_counts_check(counts):
    if (type(counts) is not list or len(counts)!=8 or
        any(type(c) is not int or c<0 for c in counts)):
        raise ValueError('INVALID_SUFFICIENT_COUNTS')
    n=sum(counts)
    # ordering (observed Z, T, Y): 000,001,010,011,100,101,110,111
    treated=counts[2]+counts[3]+counts[6]+counts[7]
    untreated=counts[0]+counts[1]+counts[4]+counts[5]
    if treated==0 or untreated==0: raise ValueError('ABSENT_TREATMENT_ARM')
    naive=(counts[3]+counts[7])/treated-(counts[1]+counts[5])/untreated
    adj=0.
    for start in (0,4):
        c0=counts[start]+counts[start+1]
        c1=counts[start+2]+counts[start+3]
        if c0==0 or c1==0:
            return n,naive,None
        adj+=(c0+c1)/n*(counts[start+3]/c1-counts[start+1]/c0)
    return n,naive,adj


def verify_report(obj):
    if not isinstance(obj,dict) or obj.get('phase')!='C14 P4E G12' or obj.get('status')!='OFFLINE_ADVERSARIAL_SYNTHETIC_RESEARCH_ONLY':
        raise ValueError('INVALID_G12_PHASE')
    des=obj.get('design',{})
    if (des.get('seeds')!=list(ALLOWED_SEEDS) or des.get('sample_sizes')!=list(ALLOWED_N)
        or des.get('scenarios')!=list(EXPECTED) or des.get('oracle_ates')!=EXPECTED
        or des.get('source_model')!='NEW_G12_NOT_G7_G9_G11'
        or des.get('predeclared_no_method_retuning') is not True):
        raise ValueError('INVALID_G12_EXPERIMENT_DESIGN')
    if obj.get('claims')!={'causal_identification_proven':False,'model_domain_authenticated':False,
          'real_world_causal_claim_authorized':False,'intervention_authorized':False,
          'windows_confinement_verified':False,'lu_host_authenticated':False}:
        raise ValueError('FALSE_G12_CAUSAL_AUTHORITY')
    records=obj.get('records')
    if not isinstance(records,list) or len(records)!=len(EXPECTED)*len(ALLOWED_N)*len(ALLOWED_SEEDS) or obj.get('dataset_count')!=len(records):
        raise ValueError('G12_WRONG_RECORD_COUNT')
    found=set();by_case=defaultdict(list)
    for r in records:
        name=r.get('scenario');n=r.get('sample_size');seed=r.get('seed')
        if (name not in EXPECTED or type(n) is not int or n not in ALLOWED_N
            or type(seed) is not int or seed not in ALLOWED_SEEDS or (name,n,seed) in found):
            raise ValueError('G12_DUPLICATE_OR_OUT_OF_DESIGN_RECORD')
        found.add((name,n,seed));count,naive,adj=independent_counts_check(r.get('counts_z_t_y'))
        if count!=n or not isclose(r.get('oracle_ate',999),EXPECTED[name],abs_tol=1e-12):
            raise ValueError('G12_ORACLE_OR_SAMPLE_MISMATCH')
        if not isfinite(naive) or not isclose(r.get('naive_risk_difference',999),naive,rel_tol=1e-12,abs_tol=1e-12):
            raise ValueError('G12_NAIVE_RESULT_MISMATCH')
        if (adj is None) != (r.get('stratified_risk_difference') is None):
            raise ValueError('G12_STRATIFIED_AVAILABILITY_MISMATCH')
        if adj is not None and not isclose(r['stratified_risk_difference'],adj,abs_tol=1e-12):
            raise ValueError('G12_STRATIFIED_RESULT_MISMATCH')
        if (r.get('observed_selection_only') is not (name=='SELECTION_COLLIDER')
            or r.get('observed_variable_is_mismeasured') is not (name=='MISMEASURED_CONFOUNDER')):
            raise ValueError('G12_ASSUMPTION_LABEL_FORGED')
        by_case[(name,n)].append((naive,adj))
    if set(obj.get('summary',{}))!={f'{s}@{n}' for s in EXPECTED for n in ALLOWED_N}:
        raise ValueError('G12_SUMMARY_CASE_SET_MISMATCH')
    for (s,n),entries in by_case.items():
        record=obj['summary'][f'{s}@{n}']
        valid=[v for _,v in entries if v is not None]
        if (record.get('attempts')!=len(entries) or record.get('adjusted_computed')!=len(valid)
            or record.get('causal_interpretation_eligible') is not (s in ('CLEAN_INTERACTION','NEGATIVE_CONTROL'))
            or record.get('outside_G9_G11_calibration_domain') is not True):
            raise ValueError('G12_AGGREGATE_CLASSIFICATION_MISMATCH')
        expected_naive=fsum(abs(x-EXPECTED[s]) for x,_ in entries)/len(entries)
        expected_strat=fsum(abs(x-EXPECTED[s]) for x in valid)/len(valid)
        if (not isclose(record['mean_absolute_naive_error'],expected_naive,abs_tol=1e-12)
            or not isclose(record['mean_absolute_stratified_error'],expected_strat,abs_tol=1e-12)):
            raise ValueError('G12_AGGREGATE_MATH_MISMATCH')
    return {'records_verified':len(records),'scenarios_verified':len(by_case),'independent_numerical_recomputation':True,
            'causal_assumptions_proven':False,'real_world_authority':False}
