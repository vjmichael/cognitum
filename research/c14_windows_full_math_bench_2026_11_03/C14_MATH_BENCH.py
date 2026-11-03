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
 """Recover a dedicated historical scratch cache from the SHA-pinned ZIP.

 The mathematical suites may overwrite archived report/diagnostic files in this
 private working copy. Verify *every* archived member before each suite/case;
 restore only changed/missing members, using an atomic same-directory replace.
 Never silently accept altered source, untrusted links, or a wrong cache marker.
 Results/logs live outside this scratch directory and are not touched.
 """
 if digest(archive)!=PIN:
  raise ValueError('Original archive SHA-256 mismatch; refusing to execute modified source')
 marker=root/'.BENCH_ORIGINAL_SHA256'
 if root.is_symlink():raise ValueError('Historical scratch root is a symlink')
 exists=root.exists()
 if exists:
  if not (marker.is_file() and not marker.is_symlink() and marker.read_text().strip()==PIN):
   raise ValueError('Working root provenance missing/invalid; refusing to overwrite: '+str(root))
 else:
  root.mkdir(parents=True)
 try:
  with zipfile.ZipFile(archive) as z:
   infos={};dirs=set();seen=set()
   for info in z.infolist():
    name=info.filename
    if info.is_dir():continue
    p=pathlib.PurePosixPath(name)
    if (not name or name.startswith('/') or '\\' in name or ':' in name
        or any(x in ('.','..') for x in p.parts) or name in seen):
     raise ValueError('Unsafe duplicate/traversing archive member: '+name)
    if ((info.external_attr>>16)&0o170000)==0o120000:
     raise ValueError('Symlink in archived source')
    seen.add(name);infos[name]=info
   if len(seen)!=1100:raise ValueError('Unexpected original CH39 member count')
   manifest=json.loads(z.read('SHA256SUMS_FULL_CH39.json'))
   if set(manifest)!=(seen-{'SHA256SUMS_FULL_CH39.json'}):
    raise ValueError('Full original archive manifest does not match ZIP member inventory')
   restored=[]
   for name,info in infos.items():
    target=root.joinpath(*pathlib.PurePosixPath(name).parts)
    for parent in target.parents:
     if parent==root.parent:break
     if parent.is_symlink():raise ValueError('Symlinked scratch path prohibited: '+str(parent))
    if target.is_symlink():raise ValueError('Symlinked original source prohibited: '+name)
    expected=manifest.get(name)
    if target.is_file() and (expected is None or digest(target)==expected):continue
    if target.exists() and not target.is_file():
     raise ValueError('Archived source path is not a regular file: '+name)
    target.parent.mkdir(parents=True,exist_ok=True)
    # Write a verified temporary replacement in the same directory. An
    # interrupted write cannot create a trusted, partially repaired file.
    fd,tmp=tempfile.mkstemp(prefix='.c14restore_',suffix='.tmp',dir=target.parent)
    try:
     with os.fdopen(fd,'wb') as out,z.open(info) as src:
      shutil.copyfileobj(src,out)
      out.flush();os.fsync(out.fileno())
     if expected is not None and digest(pathlib.Path(tmp))!=expected:
      raise ValueError('Original archive member hash mismatch: '+name)
     os.replace(tmp,target)
    finally:
     if os.path.exists(tmp):os.unlink(tmp)
    restored.append(name)
   marker.write_text(PIN+'\n',encoding='utf8')
   if exists and restored:
    print('Recovered sealed mathematical working copy:',len(restored),
          'restored/missing file(s); first:',', '.join(restored[:4]),flush=True)
   return restored
 except BaseException:
  # Never destroy an existing scratch cache; the next run may diagnose it.
  # Remove a failed *new* extraction only (no user results live here).
  if not exists:shutil.rmtree(root,ignore_errors=True)
  raise


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


def _mpfr_candidates():
 """Return bounded, well-known kit-local and sibling paths without scanning the disk.

 In real Windows use, both kits may be extracted with a nested folder or a
 duplicate-safe suffix such as `` (1)``. The previous exact sibling glob was
 too fragile and silently prevented 112 mathematical tasks from running.
 """
 seen=set()
 def add(path):
  candidate=pathlib.Path(path)
  key=os.path.normcase(os.path.abspath(str(candidate)))
  if key not in seen:
   seen.add(key)
   return candidate

 # For explicit deployments, permit a pinned runtime path from the environment.
 environment=os.environ.get('C14_BENCH_MPFR_DLL')
 if environment:
  x=add(pathlib.Path(environment).expanduser())
  if x is not None:yield x

 for root in (HERE,HERE.parent):
  x=add(root/'MPFR_Runtime'/'libmpfr-6.dll')
  if x is not None:yield x

 # The older consolidated CH39 Windows test was extracted alongside this kit
 # for the current user. Also check user Downloads if this kit was moved.
 roots=[HERE.parent]
 home=os.environ.get('USERPROFILE')
 if home: roots.append(pathlib.Path(home)/'Downloads')
 elif sys.platform=='win32':roots.append(pathlib.Path.home()/'Downloads')
 for parent in roots:
  if not parent.is_dir():continue
  try:
   children=list(parent.iterdir())
  except (PermissionError,OSError):continue
  for child in children:
   if not child.is_dir() or child.is_symlink():continue
   if not child.name.lower().startswith('cognitum_ch23_ch39_all_history_windows_regression'):
    continue
   # Default extraction, or one additional wrapper level from zip extraction.
   x=add(child/'MPFR_Runtime'/'libmpfr-6.dll')
   if x is not None:yield x
   try:
    nested=list(child.iterdir())
   except (PermissionError,OSError):continue
   for sub in nested:
    if sub.is_dir() and not sub.is_symlink() and sub.name.lower().startswith('cognitum_ch23_ch39_all_history_windows_regression'):
     x=add(sub/'MPFR_Runtime'/'libmpfr-6.dll')
     if x is not None:yield x


def mpfr_path(a):
 if a.mpfr_dll:
  p=pathlib.Path(a.mpfr_dll).expanduser().resolve()
  if p.is_dir():p=p/'libmpfr-6.dll'
  if not p.is_file():raise ValueError('Specified MPFR DLL is missing: '+str(p))
  print('MPFR: using explicit DLL',p,flush=True)
  return str(p)
 for candidate in _mpfr_candidates():
  if candidate.is_file():
   print('MPFR: discovered local runtime DLL:',candidate,flush=True)
   return str(candidate.resolve())
 if sys.platform!='win32':
  import ctypes.util
  found=ctypes.util.find_library('mpfr')
  if found:print('MPFR: discovered system runtime:',found,flush=True)
  return found
 print('MPFR: could not locate Windows libmpfr-6.dll. Searched kit, sibling regression kits, and Downloads.',flush=True)
 print('MPFR: copy the complete MPFR_Runtime folder beside this benchmark CMD, or specify --mpfr-dll.',flush=True)
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
 p.add_argument('--mpfr-dll',help='Native Windows libmpfr-6.dll OR its MPFR_Runtime directory (GMP/runtime DLLs stay together)')
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
   # Each mathematical task starts from the exact sealed input/source files,
   # even if an earlier test wrote reports into its private scratch tree.
   # Dirty files are restored atomically from the hash-pinned original ZIP.
   extract_exact(archive,root)
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
