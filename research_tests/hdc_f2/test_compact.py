"""Independent signed fixed-width oracle; native RTL and mapping remain separate gates."""
import itertools,random
import pytest
from tools.cog03f2_synthesis import ROOT, TOPS

def sx(x,w):
    x &= (1<<w)-1
    return x-(1<<w) if x&(1<<(w-1)) else x

def compact(q,p,m):
    z=[sx((((q^p)&m)>>i&1)*2+(m>>i&1),2) for i in range(64)]
    for width in range(3,9):
        z=[sx(z[i]+z[i+1],width) for i in range(0,len(z),2)]
    return z[0]

@pytest.mark.parametrize('q,p,m',[(0,0,0),(0,0,2**64-1),(0,2**64-1,2**64-1),(0,0xaaaaaaaaaaaaaaaa,2**64-1)])
def test_edges(q,p,m):
    assert compact(q,p,m)==m.bit_count()-2*((q^p)&m).bit_count()

def test_all_pairs():
    for q,p,m in itertools.product(range(4),repeat=3):
        assert compact(q,p,m)==m.bit_count()-2*((q^p)&m).bit_count()

def test_random():
    rng=random.Random(325)
    for _ in range(8192):
        q,p,m=[rng.getrandbits(64) for _ in range(3)]
        assert compact(q,p,m)==m.bit_count()-2*((q^p)&m).bit_count()

def test_interface():
    src=lambda n: ''.join((ROOT/f'hardware/hdc/{n}.sv').read_text().split('result);')[0].split('module '+n)[1].split())
    assert src('score64')==src('score64_compact') and 'score64_compact' in TOPS
