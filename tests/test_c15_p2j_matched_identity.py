"""Research-only, ID-blind matched geometry ablation safety/regression checks."""
from __future__ import annotations
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from cognitum import spatial_p2j_matched_identity as p


def line(frame, track_id, x, y=10, w=10, h=20):
    return f'{frame},{track_id},{x},{y},{w},{h},1,-1,-1,-1\n'


class C15P2JMatchedIdentity(unittest.TestCase):
    def test_ids_are_not_exposed_to_association_input(self):
        a,base=p.parsed_boxes((line(1,'0.0',10)+line(2,'0.0',12)).encode(),frames=2)
        b,changed=p.parsed_boxes((line(1,'999.0',10)+line(2,'123.0',12)).encode(),frames=2)
        self.assertEqual(a,b)
        self.assertNotEqual(base,changed)
        self.assertFalse(hasattr(a[1][0],'track_id'))
        self.assertEqual(a[1][0].original_columns_without_id,tuple(line(1,'0.0',10).strip().split(',')[0:1]+line(1,'0.0',10).strip().split(',')[2:]))

    def test_fixed_capacity_fails_closed(self):
        raw=''.join(line(1,j,j*10) for j in range(7))
        with self.assertRaisesRegex(p.MatchedIdentityRejected,'C15_CAPACITY_EXCEEDED'):
            p.parsed_boxes(raw.encode(),frames=1)

    def test_fractional_and_negative_id_rejected(self):
        for bad in ('-1','1.25','nan','inf'):
            with self.subTest(bad=bad), self.assertRaises(p.MatchedIdentityRejected):
                p.parsed_boxes(line(1,bad,10).encode(),frames=1)

    def test_one_observation_then_reassociation(self):
        dd,_=p.parsed_boxes((line(1,19,10)+line(2,99,11)).encode(),frames=2)
        mapping,counts,_=p.reassociate(dd,last_frame=2)
        self.assertEqual(mapping[1],mapping[2])
        self.assertEqual(counts['proposals'],1)
        self.assertEqual(counts['new_identity_proposals'],1)

    def test_seed_is_research_only(self):
        snap=p._scene({'cog_1':(1.,2.,3)})
        self.assertTrue(snap.research_only)
        self.assertFalse(hasattr(snap,'grants_authority'))
        self.assertEqual(snap.objects[0].position_m.x,1)

    def test_proposals_called_not_baseline_ids(self):
        dd,_=p.parsed_boxes((line(1,0,10)+line(2,1,11)).encode(),frames=2)
        with patch.object(p.association,'propose',wraps=p.association.propose) as spy:
            mapping,_,_=p.reassociate(dd,last_frame=2)
            self.assertEqual(spy.call_count,2)  # propose + verification replay
            self.assertEqual(mapping[1],mapping[2])

    def test_out_of_order_cannot_accidentally_reuse_baseline_ids(self):
        raw=(line(1,'17.0',10)+line(1,'88.0',90)+line(2,'99.0',11)+line(2,'66.0',91))
        dd,_=p.parsed_boxes(raw.encode(),frames=2)
        out,_,_=p.reassociate(dd,last_frame=2)
        self.assertEqual(out[1],out[2])
        self.assertEqual(out[1],['cog_1','cog_2'])

    def test_crossing_indistinguishable_objects_remain_ambiguous(self):
        from cognitum.proto import spatial_identity_pb2 as pb
        snap=p._scene({'cog_1':(0.,0.,1),'cog_2':(0.2,0.,1)})
        raw=line(2,77,5,0,10,20)+line(2,88,5,0,10,20)
        obs,_=p.parsed_boxes(raw.encode(),frames=2)
        request=p._request(snap,obs[2],2)
        proposal=p.association.propose(snap,request)
        self.assertEqual(proposal.decision,pb.ASSOCIATION_AMBIGUOUS)
        self.assertFalse(proposal.grants_authority)
        self.assertGreaterEqual(len(proposal.hypotheses),2)

    def test_staging_refuses_nonempty_folder(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);(root/'existing.txt').write_text('x')
            with self.assertRaisesRegex(p.MatchedIdentityRejected,'STAGE_NOT_EMPTY'):
                p.stage(Path('nonexistent'),Path('nonexistent'),root)

    def test_format_alone_cannot_prove_data_role(self):
        bad=line(1,1,10).replace('1,-1,-1,-1','1,1,1,1')
        # Parsing GT-like text alone is not a data-role validator; the input
        # comes only from a pinned, separately addressed tracker ZIP entry.
        self.assertEqual(p.parsed_boxes(bad.encode(),frames=1)[0][1][0].x,10)
        self.assertNotIn('ground_truth',p._extract_inputs.__code__.co_varnames)

    def test_pinned_original_trackeval_still_required(self):
        with self.assertRaises(Exception):
            p.evaluate(Path('unavailable'),{'sha256':{}},trackeval_root=Path('unavailable'),source_zip=Path('no.zip'))

if __name__=='__main__':unittest.main()
