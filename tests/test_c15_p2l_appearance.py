"""C15 P2L: genuine pixel-derived histogram integration with synthetic images.

Image pixels, rather than dataset GT IDs, create the test appearance evidence.
No real MOT17 frames or pretrained ReID weights are present in these tests.
"""
import io
import unittest
from PIL import Image, ImageDraw
from cognitum import spatial_p2l_appearance as a
from cognitum.spatial_p2k_dense_identity import Detection, Params, assign_all

SEQ='MOT17-TEST-RESEARCH'

def images_for(positions, colors=(240,40)):
    frames={};images={}
    for f,xy in enumerate(positions,1):
        im=Image.new('L',(180,48),128)
        draw=ImageDraw.Draw(im)
        dets=[]
        for index,x in enumerate(xy):
            draw.rectangle((x,10,x+11,21),fill=colors[index])
            dets.append(Detection(f,x,10,12,12))
        frames[f]=dets
        if xy:
            buf=io.BytesIO(); im.save(buf,format='PNG');images[f]=buf.getvalue()
    return frames,images

class P2LAppearanceTests(unittest.TestCase):
    def prepare(self, positions):
        frames,imgs=images_for(positions)
        return frames,imgs,a.descriptors_from_frames(frames,imgs,sequence=SEQ)

    def test_image_derived_vectors_are_protobuf_and_not_attested(self):
        frames,imgs,specs=self.prepare([[0,90]])
        self.assertEqual(len(specs[(1,0)].vector),128)
        self.assertFalse(specs[(1,0)].grants_authority)
        from cognitum.spatial_appearance_evidence import assess
        self.assertFalse(assess(specs[(1,0)]).independently_authenticated)
        self.assertNotEqual(tuple(specs[(1,0)].vector),tuple(specs[(1,1)].vector))
        out,counts=a.assign_with_appearance(frames,num_frames=1,sequence=SEQ,image_bytes=imgs,descriptors=specs)
        self.assertEqual(len(out[1]),2)
        self.assertEqual(counts['unattested_appearance_descriptors'],2)

    def test_crossing_position_switches_but_appearance_recovers(self):
        frames,imgs,specs=self.prepare([[0,100],[30,70],[60,40],[90,10]])
        pos,_,_=assign_all(frames,num_frames=4,mode='position')
        app,counts=a.assign_with_appearance(frames,num_frames=4,sequence=SEQ,
            image_bytes=imgs,descriptors=specs,mode='position')
        self.assertNotEqual(pos[1][0],pos[3][0])
        self.assertEqual(app[1][0],app[3][0]);self.assertEqual(app[1][0],app[4][0])
        self.assertEqual(app[1][1],app[4][1]);self.assertEqual(counts['input_boxes'],8)

    def test_no_images_fails_closed(self):
        frames,imgs,specs=self.prepare([[0,100],[10,90]])
        with self.assertRaisesRegex(a.P2LRejected,'IMAGE_FRAME_SET_MISMATCH'):
            a.assign_with_appearance(frames,num_frames=2,sequence=SEQ,image_bytes={1:imgs[1]},descriptors=specs)

    def test_misbound_image_bytes_fail_closed(self):
        frames,imgs,specs=self.prepare([[0,100],[20,80]])
        with self.assertRaisesRegex(a.P2LRejected,'DESCRIPTOR_BINDING_MISMATCH'):
            a.assign_with_appearance(frames,num_frames=2,sequence=SEQ,
                image_bytes={1:imgs[2],2:imgs[1]},descriptors=specs)

    def test_swapped_descriptors_fail_closed(self):
        frames,imgs,specs=self.prepare([[0,100]])
        swapped={(1,0):specs[(1,1)],(1,1):specs[(1,0)]}
        with self.assertRaisesRegex(a.P2LRejected,'DESCRIPTOR_BINDING_MISMATCH'):
            a.assign_with_appearance(frames,num_frames=1,sequence=SEQ,image_bytes=imgs,descriptors=swapped)

    def test_changed_encoder_digest_fails_closed(self):
        frames,imgs,specs=self.prepare([[0]])
        mutated={k:type(v).FromString(v.SerializeToString()) for k,v in specs.items()}
        mutated[(1,0)].encoder_sha256=b'F'*32
        with self.assertRaisesRegex(a.P2LRejected,'DESCRIPTOR_BINDING_MISMATCH'):
            a.assign_with_appearance(frames,num_frames=1,sequence=SEQ,image_bytes=imgs,descriptors=mutated)

    def test_duplicate_missing_extra_feature_fail_closed(self):
        frames,imgs,specs=self.prepare([[0,100]])
        for alt in ({(1,0):specs[(1,0)]},{**specs,(1,2):specs[(1,0)]}):
            with self.subTest(alt=alt),self.assertRaisesRegex(a.P2LRejected,'INCOMPLETE_OR_EXTRA_APPEARANCE'):
                a.assign_with_appearance(frames,num_frames=1,sequence=SEQ,image_bytes=imgs,descriptors=alt)

    def test_appearance_weights_and_nonfinite_rejected(self):
        frames,imgs,specs=self.prepare([[0]])
        for cfg in (a.AppearanceConfig(appearance_weight=float('nan')),
                    a.AppearanceConfig(momentum=1.1),a.AppearanceConfig(max_cosine_distance=-.1)):
            with self.subTest(cfg=cfg),self.assertRaisesRegex(a.P2LRejected,'INVALID_APPEARANCE_CONFIG'):
                a.assign_with_appearance(frames,num_frames=1,sequence=SEQ,image_bytes=imgs,descriptors=specs,config=cfg)

    def test_detection_geometry_tampering_rejected(self):
        frames,imgs,specs=self.prepare([[0]])
        other={1:[Detection(1,1,10,12,12)]}
        with self.assertRaisesRegex(a.P2LRejected,'DESCRIPTOR_BINDING_MISMATCH'):
            a.assign_with_appearance(other,num_frames=1,sequence=SEQ,image_bytes=imgs,descriptors=specs)

    def test_gap_and_expiry_are_explicit(self):
        frames,imgs,specs=self.prepare([[0],[],[8]])
        out,counts=a.assign_with_appearance(frames,num_frames=3,sequence=SEQ,image_bytes=imgs,descriptors=specs)
        self.assertEqual(out[1],out[3]);self.assertEqual(counts['frames_without_detections'],1)
        old,_,new,=out[1],counts,out[3]
        self.assertEqual(old,new)
        frames,imgs,specs=self.prepare([[0]]+[[]]*13+[[8]])
        out,_=a.assign_with_appearance(frames,num_frames=15,sequence=SEQ,image_bytes=imgs,descriptors=specs)
        self.assertNotEqual(out[1],out[15])

    def test_unusable_crop_rejected(self):
        frames,imgs=images_for([[0]])
        with self.assertRaisesRegex(a.P2LRejected,'UNUSABLE_CROP'):
            a.descriptor_from_frame(image_bytes=imgs[1],detection=Detection(1,-100,10,12,12),index=0,sequence=SEQ)

    def test_empty_observation_set_not_reported_as_success(self):
        with self.assertRaisesRegex(a.P2LRejected,'NO_APPEARANCE_OBSERVATIONS'):
            a.assign_with_appearance({},num_frames=2,sequence=SEQ,image_bytes={},descriptors={})

    def test_appearance_is_not_a_proof_of_identity(self):
        from tools.run_c15_p2l_synthetic_study import run
        by_name={r['scenario']:r for r in run()['scenarios']}
        indistinguishable=by_name['indistinguishable_appearance']
        self.assertLess(indistinguishable['id_consistency_correct_over_8']['appearance_velocity'],8)
        self.assertIsNone(indistinguishable['external_mot17_scores'])

    def test_no_comparison_to_real_mot17_without_frames(self):
        frames={1:[Detection(1,2,2,12,12)]}
        with self.assertRaisesRegex(a.P2LRejected,'IMAGE_FRAME_SET_MISMATCH'):
            a.descriptors_from_frames(frames,{},sequence=SEQ)

if __name__=='__main__':unittest.main()
