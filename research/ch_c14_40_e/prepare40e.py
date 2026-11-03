"""Hash-pin original CH39 source ZIP, then patch ONLY an ephemeral research copy.

Each patch anchor occurs exactly once; otherwise fail rather than silently
instrumenting an unknown historical source version.
"""
from __future__ import annotations
import argparse,hashlib,json,zipfile,pathlib,shutil
ROOT=pathlib.Path(__file__).resolve().parent
PIN='9e713b102982ea09fecbcfbd27bccf55d56808188bfc3e5be1ba76922000ae6b'

def sha(b):return hashlib.sha256(b).hexdigest()
def patch(text,old,new):
    if text.count(old)!=1:raise RuntimeError('Refusing changed original producer patch anchor: '+old[:90])
    return text.replace(old,new)

def instrument(out,source):
    original=source.read_bytes()
    if sha(original)!=PIN:raise ValueError('Original CH39 frozen archive hash differs from external pin')
    if out.exists():shutil.rmtree(out)
    out.mkdir(parents=True)
    with zipfile.ZipFile(source) as z:
        for name in z.namelist():
            pp=pathlib.PurePosixPath(name)
            if name.startswith('/') or '..' in pp.parts or '\\' in name:raise ValueError('Path traversal in original package')
            if not (name.startswith('CH_C14_24/') or name.startswith('CH_C14_25/') or name.startswith('CH_C14_26/') or name.startswith('CH_C14_27/') or name.startswith('CH_C14_29/')):continue
            if name.endswith('/') :continue
            dst=out/name;dst.parent.mkdir(parents=True,exist_ok=True);dst.write_bytes(z.read(name))
    proto=json.loads((out/'CH_C14_29'/'frozen_protocol.json').read_text())
    for path,h in proto['solver_source_sha256'].items():
        if sha((out/'CH_C14_29'/path).read_bytes())!=h:raise ValueError('Unpinned original CH29 solver module: '+path)
    for path,h in proto['dependency_source_sha256'].items():
        if sha((out/path).read_bytes())!=h:raise ValueError('Unpinned original CH29 dependency: '+path)
    target=out/'CH_C14_27'/'coupled27.py'
    txt=target.read_text()
    txt=patch(txt,'        for const,kappas in self.duals:\n            total=const',
                '        self._ch40e_observed=[]\n        for ch40e_qindex,(const,kappas) in enumerate(self.duals):\n            ch40e_rows=[]\n            total=const')
    txt=patch(txt,"                total=total+I.from_ends(cap.hi,cap.hi)\n            if best is None", """                total=total+I.from_ends(cap.hi,cap.hi)
                from producer_trace40e import iv_exact
                ch40e_rows.append({'p0_decimal':str(_ch40e_tangent_str),
                                   'p0':iv_exact(p0),'p_box':iv_exact(pbox),
                                   'k':iv_exact(k),'g_value':iv_exact(val),
                                   'g_slope':iv_exact(slope),'line_cap':iv_exact(cap)})
            from producer_trace40e import record_dual
            self._ch40e_observed.append(record_dual(ch40e_qindex,const,kappas,ch40e_rows,total))
            if best is None""")
    txt=patch(txt,'                p0=I(_heuristic_tangent_p(pbox,k.hi.as_float(UP),n,s))',
              '                _ch40e_tangent_str=_heuristic_tangent_p(pbox,k.hi.as_float(UP),n,s)\n                p0=I(_ch40e_tangent_str)')
    target.write_text(txt)
    solver=out/'CH_C14_29'/'solver29.py';txt=solver.read_text()
    txt=patch(txt,'            cached[idx]=capped\n            heapq.heappush',
              '            from producer_trace40e import record_node\n            record_node(rec,direct,bound,capped,cached.get(parent_id),model)\n            cached[idx]=capped\n            heapq.heappush')
    solver.write_text(txt)
    # Instrument the ACTUAL optimized direct Loewner/Fisher objective path.
    # The observer stores producer operands; it does not change any bound.
    direct=out/'CH_C14_26'/'improved_bounds.py';dx=direct.read_text()
    dx=patch(dx, "        weights=[]\n        for i,(xx,n,s) in enumerate(self.groups_const):", "        weights=[]\n        _ch40e_rows=[]\n        for i,(xx,n,s) in enumerate(self.groups_const):")
    dx=patch(dx,"            ll_cap=ll_cap+upper_point(cap)\n            wp=upper_point(w)","""            ll_cap=ll_cap+upper_point(cap)
            from producer_trace40e import iv_exact
            _ch40e_rows.append({'eta':iv_exact(eta),'p':iv_exact(p),'w':iv_exact(w),'binomial_cap':iv_exact(cap)})
            wp=upper_point(w)""")
    dx=patch(dx,"        return ll,ll_cap,Ientries,Uentries,weights,group", "        self._ch40e_rows=_ch40e_rows\n        return ll,ll_cap,Ientries,Uentries,weights,group")
    dx=patch(dx,"        logdet=I.from_ends(lower,upper).log()", "        _ch40e_det_interval=I.from_ends(lower,upper)\n        logdet=_ch40e_det_interval.log()")
    dx=patch(dx,"        full=I.from_ends(ll.lo,ll_upper)+HALF*logdet\n        return full, 'loewner_gram_plus_binomial_envelope'", """        full=I.from_ends(ll.lo,ll_upper)+HALF*logdet
        from producer_trace40e import iv_exact, mp_exact
        self._ch40e_direct={
            'rows':self._ch40e_rows, 'll':iv_exact(ll),'ll_cap':iv_exact(ll_cap),
            'F':[[iv_exact(z) for z in row] for row in F],
            'U':[[iv_exact(z) for z in row] for row in U],
            'detF':iv_exact(detF),'had':iv_exact(had),'detU':iv_exact(detU),
            'det_enclosure':iv_exact(_ch40e_det_interval),'logdet':iv_exact(logdet),
            'tangent_anchors':[{'coords':coords,'value':iv_exact(v),'grad':[iv_exact(q) for q in g]}
                               for coords,v,g in self.tangents],
            'tangent_cap':mp_exact(tangent_cap) if tangent_cap is not None else None,
            'll_upper':mp_exact(ll_upper),'full':iv_exact(full)
        }
        return full, 'loewner_gram_plus_binomial_envelope'""")
    direct.write_text(dx)
    # Helper is stored at CH_C14_27 too, which is already on original import path.
    helper=ROOT/'source'/'producer_trace40e.py'
    shutil.copy2(helper,out/'CH_C14_27'/'producer_trace40e.py')
    manifest={'external_original_zip_sha256':PIN,'original_solver_sha256':proto['solver_source_sha256']['solver29.py'],
              'original_coupled_sha256':proto['dependency_source_sha256']['CH_C14_27/coupled27.py'],
              'instrumented_solver_sha256':sha(solver.read_bytes()),'instrumented_coupled_sha256':sha(target.read_bytes()),'instrumented_direct_sha256':sha(direct.read_bytes()),
              'observer_sha256':sha(helper.read_bytes()),'status':'RESEARCH_FORK_ONLY_HISTORICAL_SOURCE_UNMODIFIED'}
    (out/'CH40E_PRODUCER_PATCH_MANIFEST.json').write_text(json.dumps(manifest,indent=2)+'\n')
    return manifest
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--archive',type=pathlib.Path,required=True);p.add_argument('--output',type=pathlib.Path,required=True);a=p.parse_args()
    print(json.dumps(instrument(a.output,a.archive),indent=2))
