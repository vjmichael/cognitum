#!/usr/bin/env python3
"""Full C14 archived ORIGINAL mathematical test suite + fresh MPFR replay bench."""
from __future__ import annotations
import argparse,ast,datetime,hashlib,importlib.util,json,os,pathlib,shutil,subprocess,sys,tempfile,time,traceback,zipfile

HERE=pathlib.Path(__file__).resolve().parent
ARCHIVE='Cognitum_CH_C14_39_Independent_MPFR_Checker_Original_CH23_2026-11-02.zip'
PIN='9e713b102982ea09fecbcfbd27bccf55d56808188bfc3e5be1ba76922000ae6b'
SUITES={23:'test_ch23.py',24:'tests',26:'tests',27:'tests',28:'tests',29:'tests',30:'tests',31:'tests',32:'tests',33:'tests'}
CASE_PHASES=('25','26','27','28','29','30','31')
DEPENDENCIES=('numpy','scipy','mpmath','pytest','cryptography')
LINUX_ONLY={32:'Linux-only journal durability and directory fsync',33:'Linux-only compacted journal filesystem durability',
34:'Linux fcntl proof anchors and filesystem recovery',35:'Linux signer account, SO_PEERCRED and kernel operations',
36:'Linux kernel-enforced ENOSPC, user namespaces and multi-UID signer',
37:'Linux distinct verifier/signer UIDs and AF_UNIX',38:'Linux four-UID attestor/signing service',
39:'Linux five-UID independent checker and signed service'}


def digest(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for block in iter(lambda:f.read(1048576),b''):h.update(block)
 return h.hexdigest()


def utc():return datetime.datetime.now(datetime.timezone.utc).isoformat()


def save(path,body):
 path.parent.mkdir(parents=True,exist_ok=True);tmp=path.with_suffix(path.suffix+'.tmp')
 tmp.write_text(json.dumps(body,sort_keys=True,indent=2,allow_nan=False)+'\n',encoding='utf8')
 os.replace(tmp,path)


def extract_exact(archive,root):
 if digest(archive)!=PIN:raise ValueError('Original archive SHA-256 mismatch; refusing to execute modified source')
 marker=root/'.BENCH_ORIGINAL_SHA256'
 if root.exists():
  if marker.is_file() and marker.read_text().strip()==PIN and (root/'CH_C14_31'/'verifier31.py').is_file():
   with zipfile.ZipFile(archive) as z:
    manifests=json.loads(z.read('SHA256SUMS_FULL_CH39.json'))
   for name,expected in manifests.items():
    target=root.joinpath(*pathlib.PurePosixPath(name).parts)
    if not target.is_file() or digest(target)!=expected:
     raise ValueError('Historical working-copy file differs from sealed archive: '+name)
   return
  raise ValueError('Working root provenance missing/invalid: '+str(root))
 root.mkdir(parents=True)
 try:
  with zipfile.ZipFile(archive) as z:
   seen=set()
   for info in z.infolist():
    name=info.filename
    if info.is_dir():continue
    p=pathlib.PurePosixPath(name)
    if not name or name.startswith('/') or '\\' in name or ':' in name or any(x in ('.','..') for x in p.parts) or name in seen:
     raise ValueError('Unsafe duplicate/traversing archive member: '+name)
    if (info.external_attr>>16)&0o170000==0o120000:raise ValueError('Symlink in archive')
    seen.add(name)
   if len(seen)!=1100:raise ValueError('Unexpected original CH39 member count')
   for info in z.infolist():
    if info.is_dir():continue
    dest=root.joinpath(*pathlib.PurePosixPath(info.filename).parts)
    dest.parent.mkdir(parents=True,exist_ok=True)
    with z.open(info) as src,open(dest,'wb') as out:shutil.copyfileobj(src,out)
  marker.write_text(PIN+'\n')
 except BaseException:
  shutil.rmtree(root,ignore_errors=True);raise


def inventory(root):
 out=[]
 for i in range(23,40):
  mods=list((root/f'CH_C14_{i}').rglob('*.py'))
  defs=[];tests=[]
  for f in mods:
   try:
    parsed=ast.parse(f.read_text(encoding='utf8'))
   except (SyntaxError,UnicodeError):continue
   for node in ast.walk(parsed):
    if isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef)):
     name=node.name
     defs.append({'source':str(f.relative_to(root)).replace('\\','/'),'name':name,'line':node.lineno})
     if name.startswith('test_'):tests.append(name)
  out.append({'phase':'CH'+str(i),'python_files':len(mods),'functions_defined':len(defs),
    'test_methods_declared':len(tests),'function_inventory':defs,
    'caveat':'Static function inventory. Tests and original-data replay do not guarantee individual coverage of every function.'})
 return out


def mpfr_path(a):
 if a.mpfr_dll:
  p=pathlib.Path(a.mpfr_dll).resolve()
  if not p.is_file():raise ValueError('Specified MPFR DLL is missing: '+str(p))
  return str(p)
 p=HERE/'MPFR_Runtime'/'libmpfr-6.dll'
 if p.is_file():return str(p.resolve())
 for sibling in HERE.parent.glob('Cognitum_CH23_CH39_All_History_Windows_Regression_*/MPFR_Runtime/libmpfr-6.dll'):
  if sibling.is_file():
   print('Detected previously validated MPFR runtime:',sibling.parent,flush=True)
   return str(sibling.resolve())
 if sys.platform!='win32':
  import ctypes.util
  return ctypes.util.find_library('mpfr')
 return None


def test_env(root,mpfr):
 env=os.environ.copy()
 dirs=[str(HERE),str(root)]+[str(root/f'CH_C14_{i}') for i in (24,25,26,27,28,29,30,31,32,33)]
 env['PYTHONPATH']=os.pathsep.join(dirs+([env['PYTHONPATH']] if env.get('PYTHONPATH') else []))
 env.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1',PYTHONUNBUFFERED='1')
 if mpfr and pathlib.Path(mpfr).is_file():env['C14_BENCH_MPFR_DLL']=str(pathlib.Path(mpfr).resolve())
 return env


def task_run(task,env,logs,timeout):
 t=time.perf_counter();log=logs/(task['name']+'.log')
 try:
  proc=subprocess.run(task['command'],cwd=task['cwd'],env=env,capture_output=True,text=True,
                      errors='replace',encoding='utf-8',timeout=timeout)
  out=proc.stdout or '';err=proc.stderr or ''
  log.write_text('EXIT: '+str(proc.returncode)+'\nCOMMAND: '+repr(task['command'])+
                 '\n--- STDOUT ---\n'+out[-45000:]+'\n--- STDERR ---\n'+err[-45000:]+'\n',encoding='utf8')
  status='PASS' if proc.returncode==0 else 'FAIL'
  result={'status':status,'exit_code':proc.returncode,'elapsed_seconds':round(time.perf_counter()-t,3),
          'log':str(log),'stderr_tail':err[-1600:]}
  if status=='PASS' and task['kind']=='original_data':
   tagged=[line.removeprefix('C14_CASE_RESULT=') for line in out.splitlines() if line.startswith('C14_CASE_RESULT=')]
   if len(tagged)!=1:result.update(status='FAIL',reason='No unique fresh mathematical replay result')
   else:
    receipt=json.loads(tagged[0]);result['proof_replay']=receipt
    if not receipt['PASS'] or receipt['scientific']!='REPLAYED_BUT_UNRESOLVED':
     result.update(status='FAIL',reason='Unexpected scientific proof status')
  if status=='PASS' and task['kind']=='unit_suite':
   import re
   match=re.search(r'Ran (\d+) tests?',err)
   if match:result['tests_executed']=int(match.group(1))
   match=re.search(r'(\d+) passed',out)
   if match:result['tests_executed']=int(match.group(1))
  return result
 except subprocess.TimeoutExpired as e:
  log.write_text('BLOCKED: per-task timeout. No acceptance recorded.\n'+str(e)+'\n',encoding='utf8')
  return {'status':'BLOCKED','reason':'per-task timeout','elapsed_seconds':round(time.perf_counter()-t,3),'log':str(log)}
 except Exception as e:
  log.write_text(traceback.format_exc(),encoding='utf8')
  return {'status':'FAIL','reason':f'{type(e).__name__}: {e}','log':str(log)}


def main():
 p=argparse.ArgumentParser(description=__doc__)
 p.add_argument('--archive',default=ARCHIVE)
 p.add_argument('--mpfr-dll',help='Native Windows libmpfr-6.dll (GMP/runtime dependencies in same directory)')
 p.add_argument('--profile',choices=('quick','full'),default='full',help='full: all 15 original cases through CH25–31, plus historical math test suites')
 p.add_argument('--case',action='append',help='Limit to one or more original frozen case IDs')
 p.add_argument('--phase',action='append',choices=[str(n) for n in range(23,40)],help='Restrict to CH phase, repeatable')
 p.add_argument('--timeout',type=int,default=1800,help='Per original case/test suite timeout in seconds; timeout is BLOCKED not PASS')
 p.add_argument('--fresh',action='store_true',help='Ignore previous PASS results, rerun everything')
 p.add_argument('--inventory-only',action='store_true',help='Only audit source inventory, no mathematical replay')
 p.add_argument('--results',default=str(HERE/'C14_MATH_RESULTS'))
 a=p.parse_args()
 archive=pathlib.Path(a.archive);archive=archive if archive.is_absolute() else HERE/archive
 if not archive.exists():print('BLOCKED: Original sealed CH39 archive not found',archive);return 2
 if a.timeout<30:p.error('timeout minimum: 30 seconds')
 output=pathlib.Path(a.results).resolve();output.mkdir(parents=True,exist_ok=True)
 logs=output/'logs';logs.mkdir(exist_ok=True)
 root=(pathlib.Path(tempfile.gettempdir())/('C14M_'+PIN[:12])) if sys.platform=='win32' else output/'original_CH23_CH39_working_copy'
 extract_exact(archive,root)
 scan=inventory(root)
 save(output/'MATH_FUNCTION_INVENTORY.json',scan)
 print('SOURCE verified: original CH39 archive hash '+PIN,flush=True)
 print('Inventory:',sum(x['python_files'] for x in scan),'Python modules;',sum(x['functions_defined'] for x in scan),'declared functions',flush=True)
 if a.inventory_only:return 0
 cases=sorted(x.stem for x in (root/'CH_C14_25'/'inputs').glob('*.json'))
 if len(cases)!=15:raise ValueError('Frozen 15-case original CH23 input inventory is incomplete')
 if a.case:
  wrong=set(a.case)-set(cases)
  if wrong:p.error('Unfrozen case(s): '+str(wrong))
  cases=sorted(set(a.case))
 if a.profile=='quick':cases=cases[:1]
 phases=set(a.phase) if a.phase else set(str(x) for x in range(23,40))
 native=mpfr_path(a);env=test_env(root,native)
 missing=[m for m in DEPENDENCIES if importlib.util.find_spec(m) is None]
 # Use all suite families, but annotate Linux-only phases explicitly.
 tasks=[];unsupported={}
 for i in sorted(phases,key=int):
  n=int(i)
  if n in LINUX_ONLY and sys.platform=='win32':
   unsupported['CH'+i]={'status':'UNSUPPORTED_PLATFORM','reason':LINUX_ONLY[n]};continue
  if n not in SUITES:continue
  part=SUITES[n]
  if n==23:cmd=[sys.executable,'-m','pytest','-q',str(root/'CH_C14_23'/'test_ch23.py')]
  else:cmd=[sys.executable,'-m','unittest','discover','-s',str(root/f'CH_C14_{n}'/part),'-p','test_*.py','-v']
  tasks.append({'name':'suite_CH'+i,'kind':'unit_suite','phase':'CH'+i,'cwd':str(root),'command':cmd})
 for i in CASE_PHASES:
  if i not in phases:continue
  for case in cases:
   tasks.append({'name':'CH'+i+'__'+case,'kind':'original_data','phase':'CH'+i,'cwd':str(root),
    'command':[sys.executable,str(HERE/'c14_case_worker.py'),'--root',str(root),'--case',case,'--phase',i]})
 suite_hash=digest(HERE/'C14_MATH_BENCH.py');worker_hash=digest(HERE/'c14_case_worker.py')
 provenance={'archive_sha256':PIN,'runner_sha256':suite_hash,'worker_sha256':worker_hash,'platform':sys.platform,
             'python':sys.version.split()[0],'mpfr':str(native),'case_filter':cases,'phase_filter':sorted(phases)}
 reportpath=output/'C14_FULL_MATH_BENCH_SUMMARY.json'
 earlier=json.loads(reportpath.read_text()) if reportpath.exists() else None
 previous=earlier.get('checks',{}) if earlier and earlier.get('provenance')==provenance and not a.fresh else {}
 current={**unsupported}
 missing_reason=[]
 if missing:missing_reason.append('Missing Python dependencies '+', '.join(missing)+'; run SETUP_DEPENDENCIES.cmd')
 if not native:missing_reason.append('No libmpfr runtime found. Copy the tested MPFR_Runtime folder into this kit.')
 for k,task in enumerate(tasks,1):
  name=task['name'];old=previous.get(name)
  if old and old['status']=='PASS':
   current[name]=old;print(f'[{k}/{len(tasks)}] REUSE PASS {name}',flush=True);continue
  needed=({'numpy','scipy','pytest'} if task['phase']=='CH23' and task['kind']=='unit_suite' else
          {'mpmath'} if task['phase']=='CH24' and task['kind']=='unit_suite' else set())
  actual_missing=sorted(needed.intersection(missing))
  if actual_missing or (not native and (task['phase']!='CH23')):
   reason=[]
   if actual_missing:reason.append('Missing Python modules '+', '.join(actual_missing)+'; run SETUP_DEPENDENCIES.cmd')
   if not native and task['phase']!='CH23':reason.append('MPFR DLL not found. Copy the MPFR_Runtime folder from the prior test kit into this folder, or pass --mpfr-dll path')
   current[name]={'status':'BLOCKED','reason':'; '.join(reason)}
  else:
   print(f'[{k}/{len(tasks)}] LIVE MATHEMATICS {name}',flush=True)
   current[name]=task_run(task,env,logs,a.timeout)
  print(f'[{k}/{len(tasks)}] {current[name]["status"]} {name}',flush=True)
  summary={'suite':'Cognitum CH23–39 complete available historical mathematical regression',
           'notice':'Original MPFR computations; not all phases can run natively on Windows and no unrestricted global optimum proven',
           'provenance':provenance,'cases':cases,'checks':current,'status':'IN_PROGRESS','last_updated_utc':utc(),
           'counts':{s:sum(v['status']==s for v in current.values()) for s in ('PASS','FAIL','BLOCKED','UNSUPPORTED_PLATFORM')},
           'scientific_release':'NO_GO','global_optimality_proven':False}
  save(reportpath,summary)
 counts=summary['counts'] if tasks else {s:sum(v['status']==s for v in current.values()) for s in ('PASS','FAIL','BLOCKED','UNSUPPORTED_PLATFORM')}
 state='FAIL' if counts['FAIL'] else 'BLOCKED' if counts['BLOCKED'] else 'PASS_PORTABLE_CHECKS_ONLY' if not counts['UNSUPPORTED_PLATFORM'] else 'PASS_PORTABLE_CHECKS__LINUX_GATES_UNSUPPORTED'
 summary.update(status=state,completed_utc=utc(),
                source_function_inventory=str(output/'MATH_FUNCTION_INVENTORY.json'),
                scope_limits=['Not every declared function has independent unit coverage',
                              'CH34-39 Linux-only trust/OS integration is not reproduced on Windows',
                              'Historical CH23 source optimizer reconstruction not equivalent to a new scientific holdout',
                              'No 0.05 bounded gap certification or unrestricted global optimum was established'])
 save(reportpath,summary)
 print('\nC14 FINAL:',state,'|',counts,'\nResult:',reportpath,flush=True)
 return 1 if counts['FAIL'] else 2 if counts['BLOCKED'] else 0

if __name__=='__main__':
 try:raise SystemExit(main())
 except Exception as e:
  print('FATAL',type(e).__name__,str(e),flush=True)
  traceback.print_exc();raise SystemExit(1)
