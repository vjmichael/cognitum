"""G15 research-only real-model-ready paired causal caller evaluation.

Usage (offline smoke): python -m tools.run_c14_p4e_g15_llm_caller_eval --dry-run
Usage (explicit model endpoint):
 python -m tools.run_c14_p4e_g15_llm_caller_eval --endpoint http://127.0.0.1:1234/v1 \
   --model local-model-id --engine lm-studio --weights Q4_K_M --kv-cache q8_0 --context 32768

Real-run results are still self-reported by a localhost endpoint and need human
semantic review. This tool has no capability dispatcher or effectful tool path.
"""
import argparse
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import sys
from cognitum import causal_llm_caller_eval as g15
from cognitum.proto import causal_llm_caller_evaluation_pb2 as pb

SOURCE_ROOT=Path(__file__).resolve().parents[1]
G14_FILE=SOURCE_ROOT/'docs/components/causal/P4E-G14-genuine-worker-smoke-evidence.json'
DEFAULT_OUTPUT=SOURCE_ROOT/'docs/components/causal/P4E-G15-caller-evaluation-evidence.json'

def scripted_reply(case,stage,mode):
    level='abstain' if (stage=='route' or mode==pb.CALLER_WITHOUT_COGNITUM or not case['safe']) else 'research_diagnostic_only'
    return json.dumps({'capability':case['capability'],'claim_level':level,'execute_action':False,
      'summary':'Only a bounded synthetic research diagnostic is available; results do not prove causality, authenticate host workers, or authorize actions.'})

def run(*,endpoint=None,model='scripted-stub',engine='unverified-local',weights='unknown',kv_cache='unknown',
        context=8192,model_fingerprint='unverified',seed=7,max_tokens=300,temperature=0.0,timeout=45):
    live=endpoint is not None
    if live and not model.strip(): raise ValueError('MODEL_ID_REQUIRED')
    if not (256<=context<=2097152 and 16<=max_tokens<=4096 and 0<=temperature<=2.0):
        raise ValueError('INVALID_INFERENCE_SETTINGS')
    transport=g15.LoopbackChatEndpoint(endpoint,timeout=timeout) if live else None
    config=pb.CallerModelConfiguration(schema_version=1,
       run_id='g15-'+hashlib.sha256((model+engine+str(seed)).encode()).hexdigest()[:12],
       model_id=model,model_fingerprint=model_fingerprint,weight_quantization=weights,
       kv_cache_quantization=kv_cache,context_window_tokens=context,
       output_token_limit=max_tokens,temperature=temperature,seed=seed,
       engine_identity=engine,protocol='openai-compatible-local-http' if live else 'deterministic-scripted-stub',
       research_only=True)
    trials=[]
    for case in g15.CASES:
        for mode in (pb.CALLER_WITHOUT_COGNITUM,pb.CALLER_WITH_COGNITUM):
            # The G14 evidence is a frozen, Linux research smoke, not authenticated.
            evidence=g15.worker_context(case['backend'],G14_FILE) if case['backend'] and mode==pb.CALLER_WITH_COGNITUM else None
            for stage in ('route','interpret'):
                present=evidence if stage=='interpret' else None
                messages=g15.prompt(case,stage,mode,present)
                wire=json.dumps(messages,sort_keys=True,separators=(',',':')).encode()
                trusted=json.dumps(present,sort_keys=True).encode() if present else b''
                if live:
                    try: reply,latency=transport.complete(model,messages,seed=seed,temperature=temperature,max_tokens=max_tokens)
                    except g15.EndpointError: reply,latency=None,0
                else:reply,latency=scripted_reply(case,stage,mode),0
                evaluated=g15.score(case=case,stage=stage,mode=mode,
                    model_reply=reply,model_called=bool(live and reply is not None),
                    elapsed_ms=latency,prompt_bytes=wire,trusted_bytes=trusted)
                row=g15.serialize_trial(evaluated);row['phase']=stage
                # Methodological caveat: the real runtime model identity is not attested.
                trials.append(row)
    modes={}
    for mode in ('CALLER_WITH_COGNITUM','CALLER_WITHOUT_COGNITUM'):
        subgroup=[x for x in trials if x['mode']==mode]
        modes[mode]={'trials':len(subgroup),
           'structural_pass':sum(x['disposition']=='CALLER_EVAL_STRUCTURAL_PASS_MANUAL_REVIEW' for x in subgroup),
           'failed_or_unavailable':sum(x['disposition']!='CALLER_EVAL_STRUCTURAL_PASS_MANUAL_REVIEW' for x in subgroup),
           'model_endpoint_replies':sum(x['model_endpoint_responded'] for x in subgroup),
           'model_requested_external_action':sum(not x['no_action_requested'] and x['disposition']!='CALLER_EVAL_MODEL_UNAVAILABLE' for x in subgroup),
           'qualified_research_diagnostics_reported':sum(x['reported_qualified_research_diagnostic'] for x in subgroup)}
    return {'milestone':'C14 P4E G15','kind':'live_local_endpoint_trial' if live else 'scripted_acceptance_only',
      'research_only':True,'local_endpoint_reply_coverage_complete':live and all(x['model_endpoint_responded'] for x in trials),
      'real_model_benchmark_independently_verified':False,
      'real_model_identity_independently_authenticated':False,
      'independent_human_semantic_review_complete':False,'external_action_grants':0,
      'scientific_worker_process_identity_authenticated':False,
      'lu_authenticated':False,'native_windows_confinement_verified':False,
      'g14_genuine_research_worker_evidence_reused_not_reexecuted':True,
      'paired_conditions_have_same_questions':True,
      'model_configuration':{
          'model_id':config.model_id,'model_fingerprint':config.model_fingerprint,
          'weight_quantization':config.weight_quantization,
          'kv_cache_quantization':config.kv_cache_quantization,
          'context_window_tokens':config.context_window_tokens,
          'max_output_tokens':config.output_token_limit,'temperature':config.temperature,
          'seed':config.seed,'engine_identity':config.engine_identity,
          'protocol':config.protocol,'config_protobuf_sha256':hashlib.sha256(config.SerializeToString(deterministic=True)).hexdigest()},
      'paired_summary':modes,'trials':trials,
      'evaluation_limits':['Scoring checks explicitly structured fields, NOT semantic truth of summary prose.',
        'No tool selected by a model is actually invoked; G14 research evidence is replayed only.',
        'Model IDs/quantization are operator-declared and not cryptographically attested.',
        'Scripted-stub results are not an LLM benchmark. Live localhost replies are not model attestation.',
        'G14 runtime evidence and G13 synthetic calibration do not share a dataset; no causal transfer claim.',
        'No permission to take actions, issue real-world causal claims, or override upstream abstention.']}

def main():
    p=argparse.ArgumentParser(description=__doc__)
    grp=p.add_mutually_exclusive_group(required=True)
    grp.add_argument('--dry-run',action='store_true',help='deterministic harness acceptance, NOT real LLM')
    grp.add_argument('--endpoint',help='explicit local OpenAI-compatible /v1 endpoint')
    p.add_argument('--model',default=None)
    p.add_argument('--engine',default='unverified-local')
    p.add_argument('--weights',default='unknown')
    p.add_argument('--kv-cache',default='unknown')
    p.add_argument('--context',type=int,default=8192)
    p.add_argument('--model-fingerprint',default='unverified')
    p.add_argument('--seed',type=int,default=7)
    p.add_argument('--max-tokens',type=int,default=300)
    p.add_argument('--temperature',type=float,default=0.0)
    p.add_argument('--timeout',type=int,default=45)
    p.add_argument('--out',type=Path,default=DEFAULT_OUTPUT)
    args=p.parse_args()
    if args.endpoint and not args.model:p.error('--model required for live endpoint trials')
    report=run(endpoint=args.endpoint,model=args.model or 'scripted-stub',engine=args.engine,
      weights=args.weights,kv_cache=args.kv_cache,context=args.context,
      model_fingerprint=args.model_fingerprint,seed=args.seed,
      max_tokens=args.max_tokens,temperature=args.temperature,timeout=args.timeout)
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(json.dumps(report,indent=2,sort_keys=True)+'\n')
    print('G15',report['kind'],'model replies:',sum(x['model_endpoint_replies'] for x in report['paired_summary'].values()),
       'trials:',len(report['trials']),'external action grants:',report['external_action_grants'])
    for name,detail in report['paired_summary'].items():print(name,detail)
    return 0 if not args.endpoint or report['local_endpoint_reply_coverage_complete'] else 2
if __name__=='__main__':sys.exit(main())
