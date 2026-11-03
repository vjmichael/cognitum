"""Adversarial CH40-C proof-rule and research-scope attestation tests.

Full original-data replay is performed once and reused only for test setup;
actual acceptance gate independently replays the full computation again.
"""
from __future__ import annotations
import base64, copy,hashlib,json,pathlib,sys,unittest,zipfile
from decimal import Decimal
from fractions import Fraction
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
ROOT=pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from verify_original40 import decode_case,ORIGINAL_ZIP_SHA256
from independent_checker40 import canonical,digest,MathematicalModel
from rule_checker40c import exact_nodes,verify_tree,audit_claim,require_independent_support_for_producer_caps
from attestation_policy40c import ResearchAttestorGate,DOMAIN,RESEARCH_SCOPE
from independent_bounds40b import taylor_upper
from independent_newton40b import check_claim,krawczyk
from batch40b import finite_fraction

ARCHIVE=ROOT/'Cognitum_CH_C14_39_Independent_MPFR_Checker_Original_CH23_2026-11-02.zip'

class Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with zipfile.ZipFile(ARCHIVE) as z:
            pins=json.loads(z.read('CH_C14_39/CH39_public_witness/frozen_pins.json'))
            cls.cert=decode_case(z,'one_event_n80_i00',pins)
        cls.proof=verify_tree(cls.cert)
        cls.secret=Ed25519PrivateKey.generate();cls.public=cls.secret.public_key()
        cls.pin=digest(cls.cert)
    def gate(self,source=ORIGINAL_ZIP_SHA256,**pins):
        return ResearchAttestorGate(pinned_checker_public_key=self.public,source_archive_sha256=source,
            case_certificate_sha256=pins or {'one_event_n80_i00':self.pin})
    def ticket(self,nonce,body_changes=None):
        b={'version':'CH40C-RESEARCH-V1','case':'one_event_n80_i00','source_archive_sha256':ORIGINAL_ZIP_SHA256,
           'certificate_sha256':self.pin,'checker_result_sha256':hashlib.sha256(canonical(self.proof)).hexdigest(),
           'nonce':nonce,'scope':RESEARCH_SCOPE,'scientific_release':'NO_GO',
           'producer_optimized_rules_fully_certified':False,'nodes_replayed':127}
        if body_changes:b.update(body_changes)
        return {'body':b,'signature_b64':base64.b64encode(self.secret.sign(DOMAIN+canonical(b))).decode()}
    def test_01_source_pinned(self):
        self.assertEqual(hashlib.sha256(ARCHIVE.read_bytes()).hexdigest(),ORIGINAL_ZIP_SHA256)
    def test_02_original_replay_127_nodes(self):
        self.assertEqual(self.proof['nodes_replayed'],127)
    def test_03_inheritance_display_exact_min(self):
        self.assertEqual(len(exact_nodes(self.cert)),64)
    def test_04_finite_result_no_promotion(self):
        self.assertFalse(self.proof['independent_finite_gap_proven']);self.assertFalse(self.proof['producer_optimized_rules_fully_certified'])
    def test_05_local_and_inherited_distinct(self):
        self.assertLess(self.proof['stats']['producer_local_displays_justified'],127)
        self.assertLess(self.proof['stats']['producer_inherited_displays_justified'],127)
    def test_06_refuse_automatic_producer_cap_promotion(self):
        with self.assertRaises(ValueError):require_independent_support_for_producer_caps(self.proof)
    def test_07_tampered_numeric_receipt(self):
        p=copy.deepcopy(self.proof);p['nodes'][1]['independent_local_upper']='999999'
        with self.assertRaises(ValueError):audit_claim(self.cert,p)
    def test_08_forged_producer_certification(self):
        p=copy.deepcopy(self.proof);p['producer_optimized_rules_fully_certified']=True
        with self.assertRaises(ValueError):audit_claim(self.cert,p)
    def test_09_forged_parent_cap_display(self):
        c=copy.deepcopy(self.cert);c['nodes'][1]['upper_bound_ceil_display']-=0.01
        with self.assertRaises(ValueError):exact_nodes(c)
    def test_10_forged_tighter_local_display_marks_unattested(self):
        c=copy.deepcopy(self.cert);c['nodes'][0]['local_upper_bound_display']=-1e90;c['nodes'][0]['upper_bound_ceil_display']=-1e90
        with self.assertRaises(ValueError):exact_nodes(c) # children were not recomputed
    def test_11_injected_newton_domain_shrink(self):
        c=copy.deepcopy(self.cert);c['nodes'][1]['effective_box'][0][0]='-9'
        with self.assertRaises(ValueError):exact_nodes(c)
    def test_12_unknown_producer_method(self):
        c=copy.deepcopy(self.cert);c['nodes'][0]['upper_method']='magic_taylor'
        with self.assertRaises(ValueError):exact_nodes(c)
    def test_13_model_digest_changed(self):
        c=copy.deepcopy(self.cert);c['model']['rows'][0]['s']=1-c['model']['rows'][0]['s']
        with self.assertRaises(ValueError):exact_nodes(c)
    def test_14_producer_promoted_to_release(self):
        c=copy.deepcopy(self.cert);c['production_release']='GO'
        with self.assertRaises(ValueError):exact_nodes(c)
    def test_15_reject_unknown_frozen_case(self):
        with self.assertRaises(ValueError):self.gate().challenge('fictitious')
    def test_16_valid_scope_receipt_live_replay(self):
        g=self.gate();n=g.challenge('one_event_n80_i00');a=g.accept(self.ticket(n),self.proof,self.cert)
        self.assertEqual(a['status'],'CH40C_RESEARCH_SCOPE_ACCEPTED')
        self.assertFalse(a['may_publish_CH39_production_witness'])
    def test_17_replayed_nonce(self):
        g=self.gate();n=g.challenge('one_event_n80_i00');ticket=self.ticket(n)
        g.accept(ticket,self.proof,self.cert)
        with self.assertRaises(ValueError):g.accept(ticket,self.proof,self.cert)
    def test_18_untrusted_signer_key(self):
        g=self.gate();n=g.challenge('one_event_n80_i00');ticket=self.ticket(n)
        foreign=Ed25519PrivateKey.generate();ticket['signature_b64']=base64.b64encode(foreign.sign(DOMAIN+canonical(ticket['body']))).decode()
        with self.assertRaises(ValueError):g.accept(ticket,self.proof,self.cert)
    def test_19_wrong_archive_commitment(self):
        g=self.gate();n=g.challenge('one_event_n80_i00')
        with self.assertRaises(ValueError):g.accept(self.ticket(n,{'source_archive_sha256':'0'*64}),self.proof,self.cert)
    def test_20_signed_but_production_scope_refused(self):
        g=self.gate();n=g.challenge('one_event_n80_i00')
        with self.assertRaises(ValueError):g.accept(self.ticket(n,{'scope':'PRODUCER_CERTIFIED'}),self.proof,self.cert,claim_scope='PRODUCER_CERTIFIED')
    def test_21_signed_global_optimum_refused(self):
        g=self.gate();n=g.challenge('one_event_n80_i00')
        with self.assertRaises(ValueError):g.accept(self.ticket(n,{'scientific_release':'GO'}),self.proof,self.cert)
    def test_22_swap_source_certificate_on_signed_ticket(self):
        g=self.gate();n=g.challenge('one_event_n80_i00')
        c=copy.deepcopy(self.cert);c['nodes'][0]['upper_bound_ceil_display']=9999
        with self.assertRaises(ValueError):g.accept(self.ticket(n),self.proof,c)
    def test_23_tampered_checker_receipt_body(self):
        g=self.gate();n=g.challenge('one_event_n80_i00')
        t=self.ticket(n);t['body']['nodes_replayed']=1
        with self.assertRaises(ValueError):g.accept(t,self.proof,self.cert)
    def test_24_taylor_encloses_frozen_midpoint(self):
        m=MathematicalModel(self.cert['model']);inc=self.cert['incumbent'];B=[]
        for x in inc:
            a=Fraction(str(x));B.append((finite_fraction(a-Fraction(1,1000)),finite_fraction(a+Fraction(1,1000))))
        self.assertGreaterEqual(taylor_upper(m,B),m.objective_bound([(x,x) for x in inc]))
    def test_25_reject_forged_newton_stationary_exclusion(self):
        m=MathematicalModel(self.cert['model']);B=[]
        for x in self.cert['incumbent']:
            a=Fraction(str(x));B.append((finite_fraction(a-Fraction(1,1000)),finite_fraction(a+Fraction(1,1000))))
        C=[['-0.01' if i==j else '0' for j in range(m.d)] for i in range(m.d)]
        with self.assertRaises(ValueError):check_claim(m,B,self.cert['root_box'],C,{'status':'NO_STATIONARY','reason':'GRADIENT_SIGN'})

if __name__=='__main__':unittest.main(verbosity=2)
