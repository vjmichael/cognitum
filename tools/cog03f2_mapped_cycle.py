"""Compile and execute the actual XC7 mapped Boolean netlist against cycle vectors.
Restricted model: supported LUT/MUX/carry primitives and synchronous FDREs,
all directly reset and clocked from the single top clock through BUFG.
Zero-delay settled logic, not a timing/unknown-state simulator. Fail closed on
unsupported primitives, parameters, drivers, clocks, reset, or combinational loops.
"""
import argparse
from collections import defaultdict, deque
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile

PORTS={'clk':('input',1),'reset':('input',1),'valid':('input',1), 'ready':('output',1),'first':('input',1),'last':('input',1),'q':('input',64),'p':('input',64),'mask':('input',64),'result_valid':('output',1),'result_ready':('input',1),'result':('output',32)}
TOPS=('score64','score64_balanced','score64_compact')

def require(ok,msg):
    if not ok: raise ValueError(msg)

def compile_plan(net,top):
    require(top in TOPS,'unsupported top')
    m=net['modules'][top];ports=m['ports'];require(set(ports)==set(PORTS),'interface drift')
    def bit(x):
        require(x in ('0','1') or type(x) is int and x>=2,'unknown/invalid bit')
        return int(x)
    def bits(xs,n):
        require(len(xs)==n,'port width');return tuple(bit(x) for x in xs)
    pp={}
    for p,(direction,n) in PORTS.items():
        require(ports[p]['direction']==direction,'port direction');pp[p]=bits(ports[p]['bits'],n)
    drivers={0,1};clock=pp['clk'][0];reset=pp['reset'][0]
    for p,(direction,n) in PORTS.items():
        if direction=='input':
            for b in pp[p]:require(b not in drivers,'multiple input drivers');drivers.add(b)
    gates=[];ffs=[];buf_clocks=set();comb_outputs=set()
    for name,c in m['cells'].items():
        typ=c['type'].lstrip('\\');params=c['parameters'];con=c['connections'];dirs=c['port_directions']
        def pin(p,n=1):return bits(con[p],n)
        def signature(inputs,outputs):
            required={**{p:'input' for p in inputs},**{p:'output' for p in outputs}}
            require(set(con)==set(required) and dirs==required,'primitive pins '+name)
        def driver(xs):
            for b in xs:require(b not in drivers,'multiple drivers '+name);drivers.add(b)
        if typ=='FDRE':
            signature(('C','CE','D','R'),('Q',));require(params=={'INIT':'x'} or params=={'INIT':'0'} or params=={'INIT':'1'},'FDRE parameter')
            require(pin('R')==(reset,),'FDRE must have direct synchronous reset')
            q,=pin('Q');driver((q,));ffs.append((q,pin('D')[0],pin('CE')[0],pin('R')[0],pin('C')[0]));continue
        if typ.startswith('LUT') and len(typ)==4 and typ[3] in '123456':
            n=int(typ[3]);names=tuple('I'+str(i) for i in range(n));signature(names,('O',));init=params.get('INIT','');require(set(params)=={'INIT'} and len(init)==2**n and set(init)<=set('01'),'LUT init')
            ins=tuple(pin(p)[0] for p in names);outs=pin('O');op=n;value=int(init,2)
        elif typ in ('INV','BUFG'):
            signature(('I',),('O',));require(not params,'buffer parameter');ins=pin('I');outs=pin('O');op=7 if typ=='INV' else 8;value=0
            if typ=='BUFG':require(ins==(clock,),'unsupported clock topology');buf_clocks.add(outs[0])
        elif typ in ('MUXF7','MUXF8'):
            signature(('I0','I1','S'),('O',));require(not params,'mux parameter');ins=pin('I0')+pin('I1')+pin('S');outs=pin('O');op=9;value=0
        elif typ=='CARRY4':
            signature(('CI','CYINIT','DI','S'),('CO','O'));require(not params,'carry parameter');ins=pin('CI')+pin('CYINIT')+pin('DI',4)+pin('S',4);outs=pin('CO',4)+pin('O',4);op=10;value=0
        else:raise ValueError('unsupported primitive '+typ)
        driver(outs);comb_outputs.update(outs);gates.append((op,value,ins,outs))
    require(len(ffs)==65 and len(buf_clocks)==1,'unexpected sequential/clock structure')
    require(all(f[4] in buf_clocks for f in ffs),'unsupported FDRE clock')
    dependencies=defaultdict(list);pending=[]
    for i,(_,_,ins,outs) in enumerate(gates):
        require(set(ins)<=drivers,'undriven gate input');deps=set(ins)&comb_outputs;pending.append(len(deps))
        for b in deps:dependencies[b].append(i)
    require(all(f[1] in drivers and f[2] in drivers for f in ffs),'undriven FF input')
    require(all(b in drivers for p,(d,_) in PORTS.items() if d=='output' for b in pp[p]),'undriven output')
    queue=deque(i for i,n in enumerate(pending) if n==0);ordered=[]
    while queue:
        i=queue.popleft();g=gates[i];ordered.append(g)
        for b in g[3]:
            for j in dependencies[b]:
                pending[j]-=1
                if pending[j]==0:queue.append(j)
    require(len(ordered)==len(gates),'combinational cycle')
    return pp,ordered,ffs,max(drivers)+1

CPP=r'''
#include <cstdint>
#include <fstream>
#include <iostream>
#include <string>
struct Gate { int op; uint64_t init; int a[10]; int o[8]; };
struct FF { int q,d,ce,r,c; };
@TABLES@
static unsigned char b[@NBITS@];
static void settle() {
    for (auto &g:gates) {
        if(g.op<=6){unsigned ix=0;for(int j=0;j<g.op;j++)ix|=unsigned(b[g.a[j]])<<j;b[g.o[0]]=(g.init>>ix)&1;}
        else if(g.op==7)b[g.o[0]]=1^b[g.a[0]];
        else if(g.op==8)b[g.o[0]]=b[g.a[0]];
        else if(g.op==9)b[g.o[0]]=b[g.a[b[g.a[2]]]];
        else {unsigned c=b[g.a[0]]|b[g.a[1]];for(int j=0;j<4;j++){unsigned s=b[g.a[6+j]];b[g.o[4+j]]=s^c;c=s?c:b[g.a[2+j]];b[g.o[j]]=c;}}
    }
}
static void edge() { unsigned char next[sizeof(ffs)/sizeof(ffs[0])];size_t j=0;for(auto &f:ffs)next[j++]=b[f.r]?0:(b[f.ce]?b[f.d]:b[f.q]);j=0;for(auto &f:ffs)b[f.q]=next[j++]; }
template<size_t N> static void put(const int (&a)[N],uint64_t x){for(size_t j=0;j<N;j++)b[a[j]]=(x>>j)&1;}
template<size_t N> static uint64_t get(const int (&a)[N]){uint64_t x=0;for(size_t j=0;j<N;j++)x|=uint64_t(b[a[j]])<<j;return x;}
int main(int argc,char **argv){
 if(argc!=2)return 2;std::ifstream f(argv[1]);if(!f)return 2;
 b[1]=1; // constants; all FDREs proven directly reset, matching TB's two reset clocks
 put(reset,1);settle();edge();settle();edge();settle();
 uint64_t qv,pv,mv,before,after;unsigned rst,v,fi,la,rr,er,ev,rv;size_t cycle=0;
 while(f>>std::dec>>rst){if(!(f>>v>>fi>>la>>rr>>std::hex>>qv>>pv>>mv>>std::dec>>er>>ev>>std::hex>>before>>std::dec>>rv>>std::hex>>after))return 3;
  if((rst|v|fi|la|rr|er|ev|rv)>1 || before>UINT32_MAX || after>UINT32_MAX)return 3;
  put(clk,0);put(reset,rst);put(valid,v);put(first,fi);put(last,la);put(result_ready,rr);put(q,qv);put(p,pv);put(mask,mv);settle();
  if(get(ready)!=er || get(result_valid)!=ev || (ev && get(result)!=before)){std::cerr<<"before cycle "<<cycle<<"\n";return 4;}
  put(clk,1);settle();edge();settle();
  if(get(result_valid)!=rv || (rv && get(result)!=after)){std::cerr<<"after cycle "<<cycle<<"\n";return 5;}
  cycle++;
 }
 if(!f.eof() || cycle<2000)return 3;
 std::cout<<"PASS mapped cycle "<<cycle<<" cycles\n";return 0;
}
'''

def render(plan):
    pp,gates,ffs,nbits=plan
    def arr(xs):return '{'+','.join(map(str,xs))+'}'
    lines=['static constexpr Gate gates[]={']
    for op,init,ins,outs in gates:lines.append('{'+str(op)+','+str(init)+'ULL,'+arr(ins)+','+arr(outs)+'},')
    lines+=['};','static constexpr FF ffs[]={']+ [arr(f)+',' for f in ffs]+['};']
    lines += ['static constexpr int '+p+'[]='+arr(bs)+';' for p,bs in pp.items()]
    return CPP.replace('@TABLES@','\n'.join(lines)).replace('@NBITS@',str(nbits))

def run(netlist,top,vectors,log):
    netlist,vectors,log=map(Path,(netlist,vectors,log));compiler=shutil.which('c++')
    if not compiler:raise RuntimeError('C++ compiler required for mapped cycle simulation')
    plan=compile_plan(json.loads(netlist.read_text()),top)
    with tempfile.TemporaryDirectory(prefix='mapped-cycle-') as td:
        src=Path(td)/'eval.cpp';exe=Path(td)/'eval';src.write_text(render(plan))
        with log.open('wb') as f:
            f.write(('engine=compiled settled XC7 primitive evaluation\ncompiler='+subprocess.check_output([compiler,'--version'],text=True).splitlines()[0]+'\nsource_sha256='+hashlib.sha256(src.read_bytes()).hexdigest()+'\n').encode());f.flush()
            subprocess.run([compiler,'-std=c++17','-O2',str(src),'-o',str(exe)],stdout=f,stderr=subprocess.STDOUT,check=True,timeout=120)
            subprocess.run([str(exe),str(vectors.resolve())],stdout=f,stderr=subprocess.STDOUT,check=True,timeout=120)
    return log.read_text()

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('netlist');p.add_argument('top');p.add_argument('vectors');p.add_argument('log');a=p.parse_args();print(run(a.netlist,a.top,a.vectors,a.log))
