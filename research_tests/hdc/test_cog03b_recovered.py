import numpy as np
import pytest
from cognitum.research.hdc_algebra import Spec
from cognitum.research.hdc_recovered.models import MODEL_REGISTRY

@pytest.mark.parametrize('family',['BSC','MAP','HRR','FHRR'])
@pytest.mark.parametrize('dimension',[256,512,1024])
@pytest.mark.parametrize('seed',[943101,943211,943321,943433,943541])
def test_historical_same_operands(family, dimension, seed):
    old=MODEL_REGISTRY[family.lower()](dimension,seed); new=Spec(family,dimension)
    rows=old.atomic(7,np.random.default_rng(seed))
    convert=lambda a:(a<0) if family=='BSC' else a.astype(new.dtype)
    a,b=rows[:2]; actual=new.bind(convert(a),convert(b))
    np.testing.assert_allclose(actual,convert(old.bind(a,b)),atol=4e-6)
    np.testing.assert_allclose(new.unbind(convert(a),actual),convert(old.unbind(a,old.bind(a,b))),atol=4e-6)
    raw=new.bundle(np.stack([convert(v) for v in rows]))
    if family=='MAP': raw=np.where(raw>=0,1,-1)
    elif family=='HRR': raw=raw/np.linalg.norm(raw)
    elif family=='FHRR': raw=raw/np.abs(raw)
    np.testing.assert_allclose(raw,convert(old.bundle(rows)),atol=4e-6)
