"""Exact byte-span compatibility transformation of the reviewed TrackEval pin."""
from hashlib import sha1,sha256
from pathlib import Path
import re

PIN="12c8791b303e0a0b50f753af204249e622d0281a"
# Original blob, independent original SHA-256, and reviewed byte offsets.
FILES={
    "trackeval/datasets/mot_challenge_2d_box.py":(
        "68aac5127374cf8d0a6f62392e7c490e6c252b79",
        "d636323991fa30e183acd898d89e26e3be04f8000b56c3f2f45b9940315af54f",
        ((11908,b"float"),(19332,b"int"),(22811,b"int"),(23284,b"int"))),
    "trackeval/metrics/hota.py":(
        "f551b766d1b4c3d4f4854bf99b04877dc1fa7c32",
        "c582255c3d36bdb49c3ceeb2a5bd912cee009190dfcfe465b4173d03aaa97d6a",
        ((1159,b"float"),(1437,b"float"),(1513,b"float"),(1712,b"float"),(1788,b"float"))),
    "trackeval/metrics/identity.py":(
        "c8c6c809989e5b620ceb3822941574018e605c70",
        "e76b1bdcbf5b193662431596a984cf70a5be32e903eb5f2a3d9921b4762f93ba",
        ((3666,b"int"),(3740,b"int"),(3811,b"int"))),
}
ALIASES={b"float":b"float64",b"int":b"int64"}
PATTERN=rb"np\.(float|int)\b"

def _postimage(before,spans,name):
    # Independent expected postimage rebuilt from the reviewed source spans,
    # not from the substitution regex. No other byte may change.
    cursor=0
    segments=[]
    for offset,kind in spans:
        old=b"np."+kind
        if kind not in ALIASES or offset<cursor or before[offset:offset+len(old)]!=old:
            raise ValueError("reviewed byte span mismatch: "+name)
        segments.extend((before[cursor:offset],b"np."+ALIASES[kind]))
        cursor=offset+len(old)
    segments.append(before[cursor:])
    expected=b"".join(segments)
    found=tuple((m.start(),m[1]) for m in re.finditer(PATTERN,before))
    if found!=spans:
        raise ValueError("unreviewed dtype alias positions: "+name)
    actual=re.sub(PATTERN,lambda m:b"np."+ALIASES[m[1]],before)
    if actual!=expected or sha256(actual).digest()!=sha256(expected).digest():
        raise ValueError("unexpected transformed source: "+name)
    return actual,sha256(expected).hexdigest()

def patch_pinned(root:Path)->dict:
    if not isinstance(root,Path) or not root.is_absolute() or root.is_symlink() or not root.is_dir():
        raise ValueError("absolute pinned TrackEval directory required")
    staged=[]
    # Preflight EVERY file before modifying any.
    for name,(blob,source_hash,spans) in FILES.items():
        path=root/name
        if (not path.is_file() or not path.resolve().is_relative_to(root.resolve())
                or any(p.is_symlink() for p in [path,*path.parents] if p!=root and root in p.parents)
                or not 0<path.stat().st_size<=200000):
            raise ValueError("unavailable reviewed file: "+name)
        before=path.read_bytes()
        before_hash=sha256(before).hexdigest()
        if (sha1(b"blob "+str(len(before)).encode()+b"\0"+before).hexdigest()!=blob
                or before_hash!=source_hash):
            raise ValueError("unreviewed TrackEval source: "+name)
        after,expected_after=_postimage(before,spans,name)
        compile(after,str(path),"exec")
        kinds=[kind for _,kind in spans]
        staged.append((path,before,after,{"file":name,"source_git_blob":blob,
                          "before_sha256":before_hash,"after_sha256":expected_after,
                          "replacements":len(spans),"by_alias":{"float":kinds.count(b"float"),"int":kinds.count(b"int")},
                          "reviewed_byte_offsets":[offset for offset,_ in spans]}))
    for path,before,_,row in staged:
        if path.read_bytes()!=before:raise ValueError("source changed after preflight: "+row["file"])
    for path,_,after,row in staged:
        path.write_bytes(after)
        if path.read_bytes()!=after:raise ValueError("post-write verification failed: "+row["file"])
    return {"source_commit":PIN,"files":[row for _,_,_,row in staged],
            "replacements":sum(row["replacements"] for _,_,_,row in staged),
            "metric_algorithms_modified":False,"transformation":"exact reviewed NumPy dtype byte spans; independent regex and postimage parity"}
