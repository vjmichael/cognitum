"""Generate read-only IBEX Minibex models for the *exact Firth objective shape*.
Compilation / execution must be checked with native IBEX. Emit NOT_RUN if unavailable.
No rounding or trust conclusion from generating a model file.
"""
from __future__ import annotations
from pathlib import Path
from time import process_time
import shutil, subprocess, hashlib


def assert_decimal_string(x):
    from decimal import Decimal
    try:
        q=Decimal(str(x))
        if not q.is_finite():raise ValueError('nonfinite')
    except Exception as e:raise ValueError('invalid frozen model literal') from e
    return str(x)


def ibex_text(case):
    rows=case.certificate['model']['rows']
    bounds=case.certificate['root_box']; p='b0,b1,b2'
    lines=[f'// CH40-M.2 original frozen CH23 data: {case.name}',
           f'// exact raw trace SHA-256: {case.source_sha256}',
           '// MODEL_ONLY: native IBEX verification not implied by this file.',
           'Variables']
    for i,(a,b) in enumerate(bounds):
        lines.append(f'  b{i} in [{assert_decimal_string(a)},{assert_decimal_string(b)}];')
    # Minibex's declaration order is constants, variables, functions, goal, constraints.
    lines.append('// Pointwise row contributions and Fisher-information weights')
    for k,r in enumerate(rows):
        x=[assert_decimal_string(v) for v in r['x']]
        z='('+' + '.join(f'({x[j]})*b{j}' for j in range(3))+')'
        n=int(r['n']);s=int(r['s'])
        lines.extend([f'function W{k:03d}({p})',
           f'  return ({n})*exp(-({z}))/(1+exp(-({z})))^2;', 'end',
           f'function L{k:03d}({p})',
           f'  return ({n})*ln(1+exp({z}))-({s})*({z});','end'])
    for i in range(3):
        for j in range(i,3):
            terms=[f'({assert_decimal_string(r["x"][i])})*({assert_decimal_string(r["x"][j])})*W{k:03d}({p})'
              for k,r in enumerate(rows)]
            lines.extend([f'function I{i}{j}({p})', '  return '+' +\n         '.join(terms)+';', 'end'])
    def I(i,j):return f'I{i}{j}({p})'
    a,b,c,d,e,f=I(0,0),I(0,1),I(0,2),I(1,1),I(1,2),I(2,2)
    determinant=f'(({a})*({d})*({f})+2*({b})*({c})*({e})-({a})*({e})^2-({d})*({c})^2-({f})*({b})^2)'
    lines+=['Minimize','  '+' +\n  '.join(f'L{k:03d}({p})' for k in range(len(rows)))+f' - 0.5*ln({determinant});',
            'Constraints',f'  {determinant} >= 0;', 'end']
    return '\n'.join(lines)+'\n'


def write_model(case,directory:Path):
    directory.mkdir(exist_ok=True,parents=True)
    path=directory/(case.name+'.bch')
    payload=ibex_text(case).encode()
    path.write_bytes(payload)
    return {'path':path.name,'sha256':hashlib.sha256(payload).hexdigest(),'bytes':len(payload),'status':'GENERATED_NOT_COMPILED'}


def probe_ibex(case,path:Path,*,timeout=5):
    binary=shutil.which('ibexopt')
    if not binary:return {'backend':'IBEX/IbexOpt','status':'NOT_RUN_DEPENDENCY_MISSING','model':path.name}
    # IBEX executable contract from upstream 2.9; never treat stdout as independent proof by itself.
    t=process_time()
    try:
        cp=subprocess.run([binary,'--rigor','-a0.05','-t'+str(timeout),str(path)],capture_output=True,text=True,timeout=timeout+30)
        return {'backend':'IBEX/IbexOpt','status':'EXECUTED_UNVERIFIED_OUTPUT','returncode':cp.returncode,
               'stdout_tail':cp.stdout[-2000:],'stderr_tail':cp.stderr[-1200:],
               'cpu_seconds_parent_process':round(process_time()-t,6),
               'scientific_certificate_imported':False}
    except subprocess.TimeoutExpired:return {'backend':'IBEX/IbexOpt','status':'TIMEOUT_NO_CERTIFICATE'}
    except Exception as e:return {'backend':'IBEX/IbexOpt','status':'NOT_ACCEPTED_RUNTIME_ERROR','reason':repr(e)[:200]}

