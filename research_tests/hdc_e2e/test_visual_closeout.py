import numpy as np
import pytest
from cognitum.research.hdc_visual_closeout import *

def test_subject_split():
    a,b,c=group_partition(np.arange(21),np.arange(21,30),3)
    assert len(a)==11 and len(b)==10 and len(c)==9 and not set(a)&set(b)
    with pytest.raises(ValueError):group_partition(np.arange(21),[20],3)

def test_imu_shape_and_replay():
    x=np.random.default_rng(3).normal(size=(4,128,9));e=IMUEncoder(32,3).fit(x)
    a=e.encode(x);assert a.shape==(4,15,32) and np.isin(a,[-1,1]).all();np.testing.assert_array_equal(a,e.encode(x))

def test_perturb_does_not_mutate():
    x=np.ones((2,128,9));a=perturb(x,'gain');assert np.allclose(a,1.35) and np.all(x==1)
    with pytest.raises(ValueError):perturb(x,'bogus')

def test_robust_envelope():
    a=np.zeros((2,20,2));a[1,:,0]=.8;y=np.zeros(20,int);g=np.arange(20)
    m=robust_calibration(a,y,g);assert m.cutoffs[0]==.8 and m.predict([[.8,2]])[0,0]

def test_quantizer_train_only():
    x=np.array([[0.,0,9],[1,10,9],[2,20,9]]);q=FeatureQuantizer().fit(x,2)
    assert q.indices.tolist()==[1,0] and q.numeric_bytes==24
    assert q.transform([[999,-999,9]]).tolist()==[[0,15]]
    assert q.lo.tolist()==[0,0]

def test_mobile_no_fallback(tmp_path):
    with pytest.raises(ValueError):FrozenMobileNet()
    p=tmp_path/'bad.pth';p.write_bytes(b'not weights')
    with pytest.raises(ValueError):FrozenMobileNet(p)

def test_feature_width_and_nonfinite():
    q=FeatureQuantizer().fit([[1,2],[3,4]],2)
    with pytest.raises(ValueError):q.transform([[1,2,3]])
    with pytest.raises(ValueError):q.transform([[1,np.nan]])


def test_hash_mismatch_reports_full_digest(tmp_path):
    p=tmp_path/'bad';p.write_bytes(b'bad artifact')
    with pytest.raises(CheckpointIntegrityError) as e:checkpoint_digest(p,'37f702c5')
    assert hashlib.sha256(p.read_bytes()).hexdigest() in str(e.value) and '37f702c5' in str(e.value)


def test_checkpoint_selection_rejects_qat_and_checks_separate_alternative(tmp_path,monkeypatch):
    from tools import cog03e2e_closeout as c
    # Synthetic bytes and test-only prefixes, never accepted as real weights.
    alternate=b'separate verified test artifact';monkeypatch.setattr(FrozenMobileNet,'PTQ_PREFIX',hashlib.sha256(alternate).hexdigest()[:8])
    def download(url,path,cap):
        path.write_bytes(b'invalid qat' if url==c.WEIGHT_URL else alternate)
        return hashlib.sha256(path.read_bytes()).hexdigest()
    monkeypatch.setattr(c,'acquire',download);records=[]
    path,variant=c.choose_checkpoint(tmp_path,True,records)
    assert variant=='ptq' and path.read_bytes()==alternate and len(records)==3
    assert [r['verified'] for r in records]==[False,False,True] and not (tmp_path/c.WEIGHT_URL.rsplit('/',1)[-1]).exists()


def test_checkpoint_selection_fails_closed_if_both_rejected(tmp_path,monkeypatch):
    from tools import cog03e2e_closeout as c
    def bad(url,path,cap):path.write_bytes(b'invalid')
    monkeypatch.setattr(c,'acquire',bad);records=[]
    with pytest.raises(RuntimeError,match='No hash-verified'):c.choose_checkpoint(tmp_path,True,records)
    assert len(records)==4 and not any(r['verified'] for r in records) and not list(tmp_path.iterdir())


def test_ptq_prefix_disjoint_from_test_and_stream():
    from tools.cog03e2e_closeout import visual_partition
    from sklearn.datasets import load_digits
    y=load_digits().target
    for seed in [1201,1207]:
        ix,tx,phases,cal=visual_partition(y,seed)
        assert len(cal)>2 and not np.intersect1d(cal,tx).size and not np.intersect1d(cal,ix).size
        assert set(y[cal])<=set(phases[0])
    with pytest.raises(ValueError,match='calibration'):FrozenMobileNet(random_smoke=True,variant='ptq')


def test_checkpoint_selection_prefers_verified_qat(tmp_path,monkeypatch):
    from tools import cog03e2e_closeout as c
    content=b'valid qat test fixture';monkeypatch.setattr(FrozenMobileNet,'PREFIX',hashlib.sha256(content).hexdigest()[:8])
    def download(url,path,cap):
        assert url==c.WEIGHT_URL;path.write_bytes(content)
    monkeypatch.setattr(c,'acquire',download);records=[]
    path,variant=c.choose_checkpoint(tmp_path,True,records)
    assert variant=='qat' and len(records)==1 and records[0]['verified'] and path.read_bytes()==content
