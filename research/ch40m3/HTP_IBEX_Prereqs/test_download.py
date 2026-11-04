import unittest,tempfile,hashlib
from pathlib import Path
import importlib.util
spec=importlib.util.spec_from_file_location('downloader',Path(__file__).parent/'Download-IBEX-Build-Tools.py');d=importlib.util.module_from_spec(spec);spec.loader.exec_module(d)
class T(unittest.TestCase):
 def test_pins_are_sha256(self):
  self.assertEqual(len(d.FILES),2)
  self.assertTrue(all(len(x['sha256'])==64 for x in d.FILES))
 def test_reuse_verified(self):
  with tempfile.TemporaryDirectory() as p:
   data=b'bytes already verified';a={'name':'a.deb','sha256':hashlib.sha256(data).hexdigest(),'path':'unused'}
   (Path(p)/a['name']).write_bytes(data)
   d.download_one(a,Path(p));self.assertEqual((Path(p)/a['name']).read_bytes(),data)
 def test_rejected_wrong_digest_without_network(self):
  with tempfile.TemporaryDirectory() as p:
   data=b'wrong';a={'name':'a.deb','sha256':'0'*64,'path':'unused'}
   (Path(p)/a['name']).write_bytes(data)
   self.assertNotEqual(d.sha256(Path(p)/a['name']),a['sha256'])
if __name__=='__main__':unittest.main()

