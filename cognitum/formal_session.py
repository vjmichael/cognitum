"""C10 P3: bounded incremental SMT transaction; deterministic, auditable outcomes.

Incremental PUSH/POP/ASSERT/CHECK statuses run within one solver process.
SAT witnesses are obtained separately and rechecked against exact snapshots.
Finite Boolean/BV UNSAT can be proved independently by exhaustive checking;
all other UNSAT claims remain explicitly unverified. No session is persistent,
no arbitrary SMT-LIB is accepted, and a host grant is still required by Lu.
"""
from __future__ import annotations
from dataclasses import dataclass
import hashlib
import os
from pathlib import Path
import re
import subprocess
import sys
import time
from .proto import formal_advanced_pb2 as a, formal_backend_pb2 as b
from .formal_backend import (SolverRegistry, ApprovedBackend, compile_run,
                             verify_backend_frame, MAX_INPUT, MAX_OUTPUT)
from .formal_finite import prove_finite_frame, verify_finite_frame, _check_formula, NotFinite
from .formal_solver import _decode, _encode

MAX_STEPS=48
MAX_CHECKS=8
MAX_ASSUMPTIONS=12
MAX_SCOPE=8
MAX_SESSION_SCRIPT=65536


def _wire(message):return message.SerializeToString(deterministic=True)


def _snapshot(plan,expressions):
    req=b.BackendRun(schema_version=1,backend_id=plan.backend_id,timeout_ms=plan.timeout_ms,trace_id=plan.trace_id)
    req.variables.extend(plan.variables)
    req.assertions.extend(expressions)
    compile_run(req)
    return req


def _contexts(plan):
    """Validate entire plan before execution and derive immutable CHECK snapshots."""
    if (plan.schema_version!=1 or len(plan.steps)>MAX_STEPS or len(plan.steps)==0 or
            not any(x.kind==a.SessionStep.CHECK for x in plan.steps)):
        raise ValueError('INVALID_SESSION_PLAN')
    if len(plan.steps)>MAX_STEPS or sum(x.kind==a.SessionStep.CHECK for x in plan.steps)>MAX_CHECKS:
        raise ValueError('SESSION_STEP_LIMIT')
    base=_snapshot(plan,[])
    header,_,_=compile_run(base)
    script=header[:header.index('(check-sat)')]
    frames=[[]]
    checks=[]
    for idx,step in enumerate(plan.steps,1):
        if not re.fullmatch('[A-Za-z0-9_.:-]{0,48}',step.label,re.ASCII):
            raise ValueError('INVALID_STEP_LABEL')
        has_assert=step.HasField('assertion')
        if step.kind==a.SessionStep.PUSH:
            if has_assert or step.assumptions or len(frames)>MAX_SCOPE:raise ValueError('INVALID_PUSH')
            frames.append([]);script+='(push 1)\n'
        elif step.kind==a.SessionStep.POP:
            if has_assert or step.assumptions or len(frames)==1:raise ValueError('INVALID_POP')
            frames.pop();script+='(pop 1)\n'
        elif step.kind==a.SessionStep.ASSERT:
            if not has_assert or step.assumptions:raise ValueError('INVALID_ASSERT_STEP')
            line=compile_run(_snapshot(plan,[step.assertion]))[0]
            assertline=next(x for x in line.splitlines() if x.startswith('(assert '))
            frames[-1].append((idx,step.assertion));script+=assertline+'\n'
        elif step.kind==a.SessionStep.CHECK:
            if has_assert or len(step.assumptions)>MAX_ASSUMPTIONS:raise ValueError('INVALID_CHECK_STEP')
            active=[item for layer in frames for item in layer]
            ass=[(i,x) for i,x in enumerate(step.assumptions,1)]
            if len(active)+len(ass)>64:raise ValueError('TOO_MANY_ACTIVE_ASSERTIONS')
            all_expr=[ex for _,ex in active]+[ex for _,ex in ass]
            req=_snapshot(plan,all_expr)
            checkscript=compile_run(_snapshot(plan,[x for _,x in ass]))[0]
            script+='(push 1)\n'
            for line in checkscript.splitlines():
                if line.startswith('(assert '):script+=line+'\n'
            script+='(check-sat)\n(pop 1)\n'
            checks.append((idx,step.label,req,tuple(active),tuple(ass)))
        else:raise ValueError('INVALID_SESSION_OPERATION')
        if len(script.encode())>MAX_SESSION_SCRIPT:raise ValueError('SESSION_SCRIPT_LIMIT')
    if len(frames)!=1:raise ValueError('UNCLOSED_PUSH_SCOPE')
    return script,checks


def _execute_status(backend:ApprovedBackend,script:str,timeout_ms:int):
    """One subprocess for all incremental status checks; independent of per-check models."""
    if backend.kind=='z3-lib':cmd=[sys.executable,'-m','cognitum.formal_z3_worker',backend.absolute_path]
    elif backend.kind=='z3-cli':cmd=[backend.absolute_path,'-in','-smt2']
    elif backend.kind=='cvc5-cli':cmd=[backend.absolute_path,'--lang=smt2','--incremental']
    else:raise ValueError('INVALID_BACKEND_KIND')
    env={k:v for k,v in os.environ.items() if k in ('SYSTEMROOT','WINDIR','PATH','PYTHONPATH')}
    cp=subprocess.run(cmd,input=script.encode(),stdout=subprocess.PIPE,stderr=subprocess.PIPE,
                      timeout=timeout_ms/1000,check=False,env=env,
                      cwd=str(Path(__file__).resolve().parents[1]))
    if cp.returncode or len(cp.stdout)>MAX_OUTPUT or len(cp.stderr)>1024:raise ValueError('SESSION_BACKEND_FAILURE')
    out=cp.stdout.decode('ascii','strict').strip()
    return out.splitlines() if out else []


def _core(run,active,assumptions):
    """Deletion-minimal finite core; *not* a claim of globally minimal MUS.

    Both the independent UNSAT check and every proposed smaller subset are
    evaluated by the standalone exhaustive verifier, never by solver rhetoric.
    """
    members=[('base',i,x) for i,x in active]+[('assumption',i,x) for i,x in assumptions]
    if len(members)>12:return (),(),False
    def unsat(subset):
        test=b.BackendRun();test.CopyFrom(run);del test.assertions[:];test.assertions.extend(x for _,_,x in subset)
        try:return _check_formula(test)[0]
        except (ValueError,NotFinite):return False
    if not unsat(members):return (),(),False
    kept=members[:]
    for item in members:
        trial=[x for x in kept if x is not item]
        if unsat(trial):kept=trial
    return tuple(i for kind,i,_ in kept if kind=='base'),tuple(i for kind,i,_ in kept if kind=='assumption'),True


def run_session_frame(frame:bytes,registry:SolverRegistry,*,host_authorized:bool=False,
                      status_runner=None,model_runner=None)->bytes:
    plan=_decode(frame,a.SessionPlan,MAX_INPUT)
    result=a.SessionResult(schema_version=1,plan_sha256=hashlib.sha256(frame).digest())
    if not host_authorized:
        result.reason_code='HOST_AUTHORIZATION_REQUIRED'
        return _encode(result,MAX_OUTPUT)
    if not registry.enabled:
        result.reason_code='REGISTRY_DISABLED'
        return _encode(result,MAX_OUTPUT)
    try:
        script,checks=_contexts(plan)
        backend=registry.backends.get(plan.backend_id)
        if backend is None:raise ValueError('BACKEND_NOT_REGISTERED')
        backend.validate()
        timeout=plan.timeout_ms or 2000
        statuses=status_runner(backend,script,timeout) if status_runner else _execute_status(backend,script,timeout)
        if not isinstance(statuses,list) or len(statuses)!=len(checks) or any(s not in ('sat','unsat','unknown') for s in statuses):
            raise ValueError('INVALID_INCREMENTAL_STATUSES')
        for (idx,label,run,active,assumptions),status in zip(checks,statuses):
            cp=result.checkpoints.add(step_index=idx,label=label,assertions_sha256=hashlib.sha256(_wire(run)).digest())
            if status=='unknown':
                cp.backend_result.CopyFrom(b.BackendResult(schema_version=1,verdict=b.UNKNOWN,verification=b.NO_EVIDENCE,
                    reason_code='SOLVER_UNKNOWN',backend_id=plan.backend_id,request_sha256=hashlib.sha256(_wire(run)).digest()))
                cp.reason_code='INCONCLUSIVE'
                continue
            checked=b.BackendResult.FromString(registry.run_frame(_wire(run),host_authorized=True,runner=model_runner))
            expect=b.SAT if status=='sat' else b.UNSAT
            if checked.verdict!=expect:
                # Status mismatches (even SAT vs UNKNOWN) cannot become proofs.
                cp.backend_result.CopyFrom(b.BackendResult(schema_version=1,verdict=b.UNKNOWN,verification=b.NO_EVIDENCE,
                    reason_code='BACKEND_STATUS_MISMATCH',backend_id=plan.backend_id,
                    request_sha256=hashlib.sha256(_wire(run)).digest()))
                cp.reason_code='INCONCLUSIVE_STATUS_MISMATCH'
                continue
            cp.backend_result.CopyFrom(checked)
            if status=='unsat':
                proof=prove_finite_frame(_wire(run));cp.finite_certificate.ParseFromString(proof)
                if verify_finite_frame(_wire(run),proof):
                    core_a,core_b,ok=_core(run,active,assumptions)
                    cp.core_assertion_step_indices.extend(core_a)
                    cp.core_assumption_indices.extend(core_b)
                    cp.core_independently_verified=ok
                    cp.reason_code='FINITE_UNSAT_CERTIFIED'
                else:cp.reason_code='UNSAT_NOT_INDEPENDENTLY_PROVEN'
            else:cp.reason_code='SAT_WITNESS_CHECKED'
        result.completed=True;result.reason_code='SESSION_COMPLETED'
    except subprocess.TimeoutExpired:
        result.ClearField('checkpoints');result.reason_code='SESSION_TIMEOUT'
    except (ValueError,OSError,UnicodeError,OverflowError) as e:
        result.ClearField('checkpoints');result.reason_code=str(e)[:64]
    return _encode(result,MAX_OUTPUT)


def verify_session_frame(plan_frame:bytes,result_frame:bytes)->bytes:
    """Reconstruct CHECK scopes and verify ALL certificates and model witnesses."""
    receipt=a.SessionReceipt(plan_sha256=hashlib.sha256(plan_frame).digest(),
                             result_sha256=hashlib.sha256(result_frame).digest())
    try:
        plan=_decode(plan_frame,a.SessionPlan,MAX_INPUT)
        result=_decode(result_frame,a.SessionResult,MAX_OUTPUT)
        _,checks=_contexts(plan)
        if (result.schema_version!=1 or not result.completed or result.plan_sha256!=receipt.plan_sha256 or
                result.host_approved or result.semantic_formalization_verified or
                result.reason_code!='SESSION_COMPLETED' or len(result.checkpoints)!=len(checks)):
            raise ValueError('UNBOUND_SESSION_RESULT')
        for cp,(idx,label,run,active,assumptions) in zip(result.checkpoints,checks):
            rf=_wire(run)
            if (cp.step_index!=idx or cp.label!=label or cp.assertions_sha256!=hashlib.sha256(rf).digest() or
                    cp.backend_result.request_sha256!=hashlib.sha256(rf).digest()):
                raise ValueError('UNBOUND_CHECKPOINT')
            if (cp.backend_result.schema_version!=1 or cp.backend_result.backend_id!=plan.backend_id or
                    cp.backend_result.host_approved or cp.backend_result.semantic_formalization_verified):
                raise ValueError('FORGED_BACKEND_ASSURANCE')
            if cp.backend_result.verdict==b.SAT:
                check=b.VerificationReceipt.FromString(verify_backend_frame(rf,_wire(cp.backend_result)))
                if not check.evidence_valid or cp.reason_code!='SAT_WITNESS_CHECKED' or cp.HasField('finite_certificate') or cp.core_independently_verified:
                    raise ValueError('INVALID_SAT_EVIDENCE')
            elif cp.backend_result.verdict==b.UNSAT:
                if (cp.backend_result.verification!=b.UNSAT_NOT_PROVEN or cp.backend_result.model or
                        cp.reason_code!='FINITE_UNSAT_CERTIFIED' or not cp.HasField('finite_certificate') or
                        not verify_finite_frame(rf,_wire(cp.finite_certificate))):
                    raise ValueError('UNSAT_NOT_CERTIFIED')
                actual_a,actual_b,ok=_core(run,active,assumptions)
                if (not ok or not cp.core_independently_verified or
                        tuple(cp.core_assertion_step_indices)!=actual_a or tuple(cp.core_assumption_indices)!=actual_b):
                    raise ValueError('INVALID_CORE_EVIDENCE')
            else:raise ValueError('UNVERIFIED_OR_INCONCLUSIVE_CHECKPOINT')
            receipt.checked_checkpoints+=1
        receipt.evidence_valid=True;receipt.reason_code='SESSION_ALL_CHECKPOINTS_RECHECKED'
    except (ValueError,NotFinite,OverflowError,UnicodeError):receipt.reason_code='INVALID_OR_UNVERIFIED_SESSION'
    return _encode(receipt,MAX_OUTPUT)
