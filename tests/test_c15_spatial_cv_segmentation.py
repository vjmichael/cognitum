"""C15 real OpenCV segmentation: reproducible masks and fail-closed inputs."""
from hashlib import sha256
from io import BytesIO
import unittest

from cognitum.spatial_cv_segmentation import segment_color


class C15SegmentationTests(unittest.TestCase):
    def test_real_host_supplied_color_mask_and_provenance(self):
        try:
            from PIL import Image
            import cv2
        except ImportError:
            self.skipTest("opencv/pillow not installed")
        image=Image.new("RGB",(16,16),(255,0,0))
        encoded=BytesIO()
        image.save(encoded,format="PNG")
        payload=encoded.getvalue()
        opts=dict(source_id="frame_source",observation_id="frame_observation",
                  frame_index=1,hsv_lower=(0,100,100),hsv_upper=(10,255,255))
        with self.assertRaises(PermissionError):
            segment_color(payload,**opts)
        r=segment_color(payload,**opts,host_admitted=True)
        self.assertEqual(r.status,"DERIVED_UNVERIFIED")
        self.assertEqual(r.foreground_pixels,256)
        self.assertEqual(r.total_pixels,256)
        self.assertEqual(r.input_sha256,sha256(payload).hexdigest())
        self.assertEqual(len(r.mask_sha256),64)
        self.assertGreaterEqual(r.component_count,1)
        self.assertEqual(segment_color(payload,**opts,host_admitted=True),r)

    def test_invalid_mask_bounds_and_image_are_refused(self):
        for bad in (((11,0,0),(10,255,255)),
                    ((-1,0,0),(10,255,255)),
                    ((0,0,0),(180,255,255)),
                    ((0.,0,0),(10,255,255))):
            with self.subTest(bounds=bad),self.assertRaises(ValueError):
                segment_color(b"image",source_id="src",observation_id="obs",
                              frame_index=1,hsv_lower=bad[0],hsv_upper=bad[1],
                              host_admitted=True)
        with self.assertRaises(ValueError):
            segment_color(b"not_an_image",source_id="src",observation_id="obs",
                          frame_index=1,hsv_lower=(0,0,0),
                          hsv_upper=(10,255,255),host_admitted=True)


if __name__=="__main__":
    unittest.main()
