"""Research-only execution of intact classical hdlib wheel modules.
Normal hdlib.model import eagerly imports mandatory quantum dependencies.
Use a fresh isolated subprocess for this adapter, never production.
"""
import hashlib,importlib,importlib.machinery,os,sys,types,zipfile
from pathlib import Path
WHEEL_SHA='f71b49443e5324a67d33138845767cabe39618a29c95b49ac3aa21b8ca91c421'
def load_classical(wheel):
    p=Path(wheel).resolve()
    if hashlib.sha256(p.read_bytes()).hexdigest()!=WHEEL_SHA:raise ValueError('unreviewed wheel')
    if any(s=='hdlib' or s.startswith('hdlib.') for s in sys.modules):raise RuntimeError('fresh interpreter required')
    with zipfile.ZipFile(p) as z:
        if z.testzip() is not None:raise ValueError('wheel CRC')
    # Exact wheel source, no edits, no fake quantum modules. Skip only eager model initializer.
    sys.path.insert(0,str(p))
    h=importlib.import_module('hdlib');assert h.__version__=='2.1.0'
    pkg=types.ModuleType('hdlib.model');pkg.__path__=[os.path.join(str(p),'hdlib','model')];pkg.__package__='hdlib.model';pkg.__spec__=importlib.machinery.ModuleSpec('hdlib.model',loader=None,is_package=True);pkg.__spec__.submodule_search_locations=pkg.__path__;sys.modules[pkg.__name__]=pkg;h.model=pkg
    mods={k:importlib.import_module('hdlib.model.'+k) for k in ('regression','clustering','graph')}
    if any(not os.path.normcase(os.path.normpath(str(m.__file__))).startswith(os.path.normcase(str(p))+os.sep) for m in mods.values()):raise RuntimeError('module source mismatch')
    return mods

def load_classifier(wheel):
    """Execute the exact classical class AST and its original classical imports.

    The reviewed wheel eagerly imports unrelated quantum dependencies. No fake
    quantum modules or rewrites of the classical methods; normal full-package
    import remains a separate dependency gate. Fresh subprocess only.
    """
    import ast
    p=Path(wheel).resolve()
    mods=load_classical(p)
    name='hdlib.model.classification'
    with zipfile.ZipFile(p) as z:
        source=z.read('hdlib/model/classification.py').decode('utf8')
    parsed=ast.parse(source)
    allowed={'copy','itertools','multiprocessing','os','statistics','math','functools','typing','contextlib','numpy','sklearn.metrics','sklearn.model_selection','hdlib','hdlib.space','hdlib.vector','hdlib.arithmetic'}
    nodes=[];classes=[]
    for node in parsed.body:
        if isinstance(node,ast.Import):
            if all(a.name in allowed for a in node.names):nodes.append(node)
        elif isinstance(node,ast.ImportFrom):
            if node.module in allowed and node.level==0:nodes.append(node)
        elif isinstance(node,ast.ClassDef) and node.name=='ClassificationModel':
            nodes.append(node);classes.append(node)
    if len(classes)!=1:raise RuntimeError('class source drift')
    module=types.ModuleType(name);module.__file__=os.path.join(str(p),'hdlib','model','classification.py');module.__package__='hdlib.model';module.__spec__=importlib.machinery.ModuleSpec(name,loader=None)
    sys.modules[name]=module
    try:exec(compile(ast.Module(body=nodes,type_ignores=[]),module.__file__,'exec'),module.__dict__)
    except Exception:sys.modules.pop(name,None);raise
    sys.modules['hdlib.model'].classification=module
    sys.modules['hdlib.model'].ClassificationModel=module.ClassificationModel
    return mods,module.ClassificationModel
