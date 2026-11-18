"""Closed-world structural tests for the compiled mapped-netlist engine."""
import copy
import pytest
from tools.cog03f2_mapped_cycle import PORTS,compile_plan,render

def fixture():
    ports={};n=2;cells={}
    for p,(direction,w) in PORTS.items():
        ports[p]={'direction':direction,'bits':list(range(n,n+w))};n+=w
    def cell(name,typ,ins,outs,params=None):
        cells[name]={'type':typ,'parameters':params or {},'connections':{**ins,**outs},'port_directions':{**dict.fromkeys(ins,'input'),**dict.fromkeys(outs,'output')}}
    b=lambda p:ports[p]['bits']
    clock=n;n+=1;cell('buf','BUFG',{'I':b('clk')},{'O':[clock]})
    for i in range(65):
        q=(b('result_valid')+b('result'))[i] if i<33 else n+i
        cell('ff'+str(i),'FDRE',{'C':[clock],'R':b('reset'),'CE':['1'],'D':['0']},{'Q':[q]},{'INIT':'x'})
    cell('ready','LUT2',{'I0':b('result_valid'),'I1':b('result_ready')},{'O':b('ready')},{'INIT':'1101'})
    return {'modules':{'score64':{'ports':ports,'cells':cells}}}

def test_compile_plan():
    pp,gates,ffs,n=compile_plan(fixture(),'score64');assert len(ffs)==65 and len(gates)==2
    assert 'static constexpr Gate gates[]' in render((pp,gates,ffs,n))

@pytest.mark.parametrize('defect',['unknown','clock','reset','driver','cycle','lut','undriven'])
def test_invalid_netlist_rejected(defect):
    x=fixture();c=x['modules']['score64']['cells'];p=x['modules']['score64']['ports']
    if defect=='unknown':c['ready']['type']='unreviewed'
    elif defect=='clock':c['ff0']['connections']['C']=p['valid']['bits']
    elif defect=='reset':c['ff0']['connections']['R']=['0']
    elif defect=='driver':c['ff1']['connections']['Q']=c['ff0']['connections']['Q']
    elif defect=='cycle':c['ready']['connections']['I0']=p['ready']['bits']
    elif defect=='lut':c['ready']['parameters']['INIT']='x101'
    elif defect=='undriven':c['ready']['connections']['I0']=[99999]
    with pytest.raises(ValueError):compile_plan(x,'score64')
