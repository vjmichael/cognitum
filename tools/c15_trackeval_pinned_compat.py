"""Exact three-blob compatibility transformation of the reviewed TrackEval pin."""
from hashlib import sha1,sha256
from pathlib import Path
import re

PIN="12c8791b303e0a0b50f753af204249e622d0281a"
FILES={
    "trackeval/datasets/mot_challenge_2d_box.py":("68aac5127374cf8d0a6f62392e7c490e6c252b79",1,3,"7b7278435e15d441896536deaba1abe49373356de2e318f534b82ba86b671d66"),
    "trackeval/metrics/hota.py":("f551b766d1b4c3d4f4854bf99b04877dc1fa7c32",5,0,"65de74d7cce237bab40cdb0c017cb77d4524256ce70aabd47c602e180228a8eb"),
    "trackeval/metrics/identity.py":("c8c6c809989e5b620ceb3822941574018e605c70",0,3,"ac3cd3b9355631684852b159488cb5c6a2e7336914c88f5f03c6a703237836e0"),
}
ALIASES={b"float":b"float64",b"int":b"int64"}

def patch_pinned(root:Path)->dict:
    if not isinstance(root,Path) or not root.is_absolute() or root.is_symlink() or not root.is_dir():
        raise ValueError("absolute pinned TrackEval directory required")
    staged=[]
    # Preflight EVERY file before modifying any.
    for name,(blob,n_float,n_int,expected_after) in FILES.items():
        path=root/name
        if (not path.is_file() or not path.resolve().is_relative_to(root.resolve())
                or any(p.is_symlink() for p in [path,*path.parents] if p!=root and root in p.parents)
                or not 0<path.stat().st_size<=200000):
            raise ValueError("unavailable reviewed file: "+name)
        before=path.read_bytes()
        if sha1(b"blob "+str(len(before)).encode()+b"\0"+before).hexdigest()!=blob:
            raise ValueError("unreviewed TrackEval source: "+name)
        matches=re.findall(rb"np\.(float|int)\b",before)
        if matches.count(b"float")!=n_float or matches.count(b"int")!=n_int:
            raise ValueError("reviewed alias count changed: "+name)
        after=re.sub(rb"np\.(float|int)\b",lambda m:b"np."+ALIASES[m[1]],before)
        if sha256(after).hexdigest()!=expected_after:raise ValueError("unexpected transformed source")
        compile(after,str(path),"exec")
        staged.append((path,after,{"file":name,"source_git_blob":blob,
                          "before_sha256":sha256(before).hexdigest(),"after_sha256":expected_after,
                          "replacements":len(matches),"by_alias":{"float":n_float,"int":n_int}}))
    for path,after,_ in staged:path.write_bytes(after)
    return {"source_commit":PIN,"files":[row for _,_,row in staged],
            "replacements":sum(row["replacements"] for _,_,row in staged),
            "metric_algorithms_modified":False,"transformation":"removed NumPy dtype aliases only"}
