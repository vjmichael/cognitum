"""Cognitum-only adapter tests; actual reference workers, never installed Lu."""
from dataclasses import replace
import hashlib
import unittest

try:
    import numpy
    from google.protobuf import message
except ModuleNotFoundError:
    raise unittest.SkipTest('optional scientific dependencies absent')

from cognitum.mel import lu_adapter as bridge, admission as a, native as n
from cognitum.mel import engines as e, engines_pb2 as ep, model_engines as m
from cognitum.mel import model_reference as r, intent_reference as ir
from cognitum.mel.engine_limits import HdcLimits, KanLimits
from cognitum.registry import Registry
from cognitum.runtime import Runtime

S = a.Scope('adapter-session','w','u','turn')
VFA = {'axes':[{'name':'x','unit':'1'}], 'domain':[{'lower':-1,'upper':1}],
       'terms':[{'center':[0],'width':[1],'weight':2}], 'constant':0,
       'output_unit':'1','points':[[.5]]}
HDC = {'probe':'101101','candidates':['101001','111101','000000']}
APP = m.Approval(m.Checkpoint(m.checkpoint_wire([ep.KanLayer(
    inputs=1, outputs=1, knots=3, basis=ep.RBF, grid=[-1.,0.,1.],
    coefficients=[0.,2.,0.], mask=[1.])])), 'adapter-test-review')


class AdapterTests(unittest.TestCase):
    def setUp(self):
        self.registry = Registry()
        self.registry.install(n.NativeVFAPlugin, enabled=True)
        self.registry.install(e.EnginePlugin, enabled=True)
        for op in bridge.OPERATIONS:
            self.registry.nominate(op,n.NAME if op in n.OP else e.NAME)
        self.host = a.Admission(Runtime(self.registry),S.session,
                enable_engines=True,enable_model_codecs=True)
        self.addCleanup(self.host.close)

    def setup_call(self,op,args,threshold=None,component=0):
        route=next(x for x in a.routes(include_engines=True) if x.operation==op)
        meta=next(x for x in bridge.proposal()['routes'] if x['operation']==op)
        allowed=r.Allowed((op,),APP if op=='kan.evaluate' else None)
        intent=ir.Intent(S,op,r.canonical(args),threshold,
                         APP.checkpoint.identity if op=='kan.evaluate' else None,component)
        raw=r.canonical({'tool':route.public_name,'arguments':args})
        return intent,allowed,route,meta['codec_sha256'],raw

    def prepare(self,op,args,threshold=None,component=0):
        return bridge.prepare(self.registry,*self.setup_call(op,args,threshold,component),
                              request_id='adapter-call')

    def execute(self,p):
        op=p.route.operation
        if op=='kan.evaluate':
            self.host.approve_checkpoint(S,APP.checkpoint.wire,
                expected_sha256=APP.checkpoint.identity,review_id=APP.review_id)
        limits=a.Limits(timeout_ms=10000) if op in n.OP else (
            KanLimits(timeout_ms=10000) if op=='kan.evaluate'
            else HdcLimits(timeout_ms=10000))
        grant=self.host.issue(S,p.route,limits,ttl_ms=60000,
            model_codec=op not in n.OP,
            checkpoint_sha256=APP.checkpoint.identity if op=='kan.evaluate' else None)
        return self.host.execute(S,grant,'adapter-call',p.wire,timeout_ms=10000)

    def test_proposal_is_inert_and_canonical(self):
        x=bridge.proposal()
        self.assertEqual(len(x['routes']),5)
        for k in ('installable','registered','model_advertised','execution_authorized'):
            self.assertIs(x[k],False)
        for item in x['routes']:
            self.assertEqual(item['required_effect'],'compute_only')
            self.assertTrue(item['input_type_url'].startswith('type.googleapis.com/'))
        x['routes'].clear()
        self.assertEqual(len(bridge.proposal()['routes']),5)

    def test_actual_vfa(self):
        p=self.prepare('vfa.evaluate',VFA,1.5)
        receipt=self.execute(p)
        x=bridge.verify_host_retained_receipt(p,receipt)
        self.assertTrue(x['ok'],x)
        self.assertEqual(x['candidate']['answer'],'above')
        self.assertIs(x['publication_authorized'],False)

    def test_actual_gradient(self):
        p=self.prepare('vfa.gradient',VFA,-.5)
        x=bridge.verify_host_retained_receipt(p,self.execute(p))
        self.assertTrue(x['ok'],x)
        self.assertEqual(x['candidate']['answer'],'below')

    def test_actual_hdc_query_all_ties(self):
        p=self.prepare('hdc.query',HDC)
        x=bridge.verify_host_retained_receipt(p,self.execute(p))
        self.assertTrue(x['ok'],x)
        self.assertEqual(x['candidate']['answer'],[0,1])

    def test_actual_hdc_binding(self):
        p=self.prepare('hdc.bind',{'left':'0101','right':'0011'})
        x=bridge.verify_host_retained_receipt(p,self.execute(p))
        self.assertTrue(x['ok'],x)
        self.assertEqual(x['candidate']['answer'],'0110')

    def test_actual_pinned_kan(self):
        p=self.prepare('kan.evaluate',{'points':[[.5]]},1.5)
        x=bridge.verify_host_retained_receipt(p,self.execute(p))
        self.assertTrue(x['ok'],x)
        self.assertEqual(x['candidate']['answer'],'above')

    def test_prepare_rejects_bad_intent_and_codec(self):
        i,al,route,codec,raw=self.setup_call('hdc.query',HDC)
        for rr,cc,txt in (
            (route,'0'*64,raw),
            (replace(route,descriptor_sha256='0'*64),codec,raw),
            (route,codec,r.canonical({'tool':route.public_name,
                     'arguments':dict(HDC,probe='000000')})),
            (route,codec,'{"tool":"shell_exec","arguments":{}}'),
            (route,codec,'{"tool":"mel_hdc_query","arguments":{},"grant":true}')):
            with self.subTest(txt=txt,codec=cc):
                with self.assertRaises(ValueError):
                    bridge.prepare(self.registry,i,al,rr,cc,txt,request_id='adapter-call')
        self.assertEqual(len(self.host._seen),0)

    def test_signed_zero_wire_mismatch(self):
        i,al,route,codec,_=self.setup_call('kan.evaluate',{'points':[[0.]]},1.5)
        raw=r.canonical({'tool':route.public_name,'arguments':{'points':[[-0.]]}})
        with self.assertRaises(ValueError):
            bridge.prepare(self.registry,i,al,route,codec,raw,request_id='adapter-call')

    def test_wrong_component_and_checkpoint(self):
        with self.assertRaises(ValueError):
            self.prepare('vfa.evaluate',VFA,1.5,component=1)
        i,al,route,codec,raw=self.setup_call('kan.evaluate',{'points':[[.5]]},1.5)
        with self.assertRaises(ValueError):
            bridge.prepare(self.registry,replace(i,checkpoint='0'*64),
                al,route,codec,raw,request_id='adapter-call')

    def test_receipt_identity_and_refusal(self):
        p=self.prepare('hdc.query',HDC)
        rec=self.execute(p)
        for bad in (replace(rec,scope=replace(S,workspace='other')),
                    replace(rec,request_id='other'),
                    replace(rec,request_sha256='0'*64),
                    replace(rec,result_sha256='0'*64),
                    replace(rec,status='cancelled')):
            with self.assertRaises(ValueError):
                bridge.verify_host_retained_receipt(p,bad)
        denied=replace(rec,status='cancelled',result_frame=None,result_sha256=None)
        out=bridge.verify_host_retained_receipt(p,denied)
        self.assertFalse(out['ok'])
        self.assertIsNone(out['result'])
        self.assertFalse(out['publication_authorized'])

    def test_hash_consistent_wrong_hdc_result_refused(self):
        p=self.prepare('hdc.query',HDC)
        rec=self.execute(p)
        frame=ep.EngineResult.FromString(rec.result_frame)
        frame.query.best_index[:]=[2]
        raw=frame.SerializeToString(deterministic=True)
        bad=replace(rec,result_frame=raw,result_sha256=hashlib.sha256(raw).hexdigest())
        with self.assertRaises(ValueError):
            bridge.verify_host_retained_receipt(p,bad)


if __name__ == '__main__':
    unittest.main()
