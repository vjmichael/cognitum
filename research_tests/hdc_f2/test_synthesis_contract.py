import random, json, zipfile
from pathlib import Path
import pytest
from tools.cog03f2_synthesis import balanced_count,cell_counts, executable, ROOT

@pytest.mark.parametrize('x',[0,1,(1<<64)-1,1<<63,0xaaaaaaaaaaaaaaaa,0x5555555555555555])
def test_edge_counts(x):assert balanced_count(x)==x.bit_count()

def test_masked_random():
    rng=random.Random(812)
    for _ in range(4096):
        q,p,m=(rng.getrandbits(64) for _ in range(3))
        assert balanced_count(m)-2*balanced_count((q^p)&m)==sum((1 if ((q>>i)&1)==((p>>i)&1) else -1) for i in range(64) if m>>i&1)

@pytest.mark.parametrize('x',[-1,1<<64])
def test_count_range(x):
    with pytest.raises(ValueError):balanced_count(x)

def net(*types):return {'modules':{'score64':{'cells':{str(i):{'type':t} for i,t in enumerate(types)}}}}

def test_mapped_counts():
    result=cell_counts(net('LUT6','LUT6_2','FDRE','FDSE','CARRY4'),'score64')
    assert result['lut']==2 and result['ff']==2 and result['carry4']==1

@pytest.mark.parametrize('types',[(),('LUT6',),('FDRE','LUT6','$add'),('FDRE','LUT6','blackbox')])
def test_reject_invalid_mapping(types):
    with pytest.raises(ValueError):cell_counts(net(*types),'score64')

def test_missing_tools(monkeypatch):
    monkeypatch.setattr('tools.cog03f2_synthesis.shutil.which',lambda n:None)
    with pytest.raises(RuntimeError,match='no synthetic result'):executable('yosys')

def test_rtl_port_contract():
    # A source-interface check, NOT simulation.
    a=(ROOT/'hardware/hdc/score64.sv').read_text().split('result);')[0].split('module score64')[1]
    b=(ROOT/'hardware/hdc/score64_balanced.sv').read_text().split('result);')[0].split('module score64_balanced')[1]
    assert "".join(a.split())=="".join(b.split())
