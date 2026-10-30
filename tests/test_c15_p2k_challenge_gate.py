"""P2K staging and provenance: fail-closed tests with tiny synthetic archives."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import zipfile
from cognitum import spatial_p2k_challenge_gate as g

SEQINFO='[Sequence]\nname={seq}\nimDir=img1\nframeRate=30\nseqLength=4\nimWidth=640\nimHeight=480\nimExt=.jpg\n'
GT='1,1,10,20,30,40,1,1,1\n2,1,11,20,30,40,1,1,1\n'
PRED='1,{tid},10,20,30,40,1,-1,-1,-1\n2,{tid},11,20,30,40,1,-1,-1,-1\n'

def make_archives(where, ids=(0,10,300), tamper_gt=False, over_capacity=False):
    data=Path(where)/'data.zip';labels=Path(where)/'labels.zip'
    with zipfile.ZipFile(data,'w') as dz,zipfile.ZipFile(labels,'w') as lz:
        for ix,seq in enumerate(g.SEQUENCES):
            src=f'data/gt/mot_challenge/MOT17-train/{seq}/'
            gt=(GT+'3,1,12,20,30,40,1,1,1\n' if tamper_gt and ix==0 else GT).encode()
            info=SEQINFO.format(seq=seq).encode()
            dz.writestr(src+'gt/gt.txt',gt);dz.writestr(src+'seqinfo.ini',info)
            lz.writestr(f'train/{seq}/gt/gt.txt',GT)
            lz.writestr(f'train/{seq}/seqinfo.ini',info)
            pred=PRED.format(tid=ids[ix])
            if over_capacity and ix==0:
                pred+=''.join(f'3,{j},10,20,30,40,1,-1,-1,-1\n' for j in range(65))
            dz.writestr(f'data/trackers/mot_challenge/MOT17-train/MPNTrack/data/{seq}.txt',pred)
    return data,labels

class P2KGate(unittest.TestCase):
    def test_geometry_and_scores_preserved_id_only_change(self):
        with tempfile.TemporaryDirectory() as tmp:
            data,labels=make_archives(tmp)
            root=Path(tmp)/'stage'
            r=g.stage(data_zip=data,labels_zip=labels,out_dir=root)
            self.assertTrue(r['source_ids_exposed_to_associator'] is False)
            self.assertEqual(len(r['sequences']),3)
            for seq in g.SEQUENCES:
                orig=(root/f'trackers/MOT17-train/{g.TRACKERS[0]}/data/{seq}.txt').read_text().splitlines()
                self.assertEqual(len(orig),2)
                for name in g.TRACKERS[1:]:
                    trial=(root/f'trackers/MOT17-train/{name}/data/{seq}.txt').read_text().splitlines()
                    self.assertEqual(len(trial),len(orig))
                    for a,b in zip(orig,trial):
                        aa=a.split(',');bb=b.split(',')
                        self.assertEqual(aa[0],bb[0]);self.assertEqual(aa[2:],bb[2:])
                self.assertEqual((root/f'gt/MOT17-train/{seq}/gt/gt.txt').read_text(),GT)

    def test_changing_original_ids_does_not_change_candidates(self):
        with tempfile.TemporaryDirectory() as tmp:
            d,l=make_archives(tmp,ids=(0,10,300));p=Path(tmp)
            g.stage(data_zip=d,labels_zip=l,out_dir=p/'a')
            d2,l2=make_archives(tmp,ids=(32,999,2))
            g.stage(data_zip=d2,labels_zip=l2,out_dir=p/'b')
            for seq in g.SEQUENCES:
                for name in g.TRACKERS[1:]:
                    rel=f'trackers/MOT17-train/{name}/data/{seq}.txt'
                    self.assertEqual((p/'a'/rel).read_bytes(),(p/'b'/rel).read_bytes())

    def test_independent_ground_truth_mismatch_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            d,l=make_archives(tmp,tamper_gt=True)
            with self.assertRaisesRegex(g.P2KRejected,'INDEPENDENT_MOT17_LABELS_MISMATCH'):
                g.stage(data_zip=d,labels_zip=l,out_dir=Path(tmp)/'a')

    def test_density_overflow_rejected_not_skipped(self):
        with tempfile.TemporaryDirectory() as tmp:
            d,l=make_archives(tmp,over_capacity=True)
            with self.assertRaisesRegex(Exception,'DENSITY_EXCEEDS_CAPACITY'):
                g.stage(data_zip=d,labels_zip=l,out_dir=Path(tmp)/'a')

    def test_nonempty_stage_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            d,l=make_archives(tmp);root=Path(tmp)/'stage';root.mkdir();(root/'sentinel').write_text('x')
            with self.assertRaisesRegex(g.P2KRejected,'OUTPUT_DIRECTORY_NOT_EMPTY'):
                g.stage(data_zip=d,labels_zip=l,out_dir=root)

    def test_evaluator_rejects_tamper_and_stale_outputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            d,l=make_archives(tmp);root=Path(tmp)/'stage'
            r=g.stage(data_zip=d,labels_zip=l,out_dir=root)
            with patch.object(g.rd,'verify_pinned_trackeval_source',return_value={'commit':'pinned'}):
                summary=root/'trackers/MOT17-train/MPNTrackOriginal/pedestrian_summary.txt'
                summary.write_text('HOTA MOTA IDF1\n1 1 1\n')
                with self.assertRaisesRegex(g.P2KRejected,'STALE_EVALUATOR_OUTPUT'):
                    g.evaluate(out_dir=root,evidence=r,trackeval_root=Path(tmp),source_zip=d)
                summary.unlink()
                target=root/'gt/MOT17-train'/g.SEQUENCES[0]/'gt/gt.txt'
                target.write_bytes(b'altered')
                with self.assertRaisesRegex(g.P2KRejected,'STAGED_DATA_CHANGED'):
                    g.evaluate(out_dir=root,evidence=r,trackeval_root=Path(tmp),source_zip=d)

if __name__=='__main__':unittest.main()
