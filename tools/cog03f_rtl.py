"""Deterministic independent cycle oracle and mandatory Icarus simulation.
Oracle alone is not RTL execution. No synthesis or board interaction.
"""
from pathlib import Path
import argparse,hashlib,json,random,shutil,subprocess,tempfile
ROOT=Path(__file__).resolve().parents[1]


def vectors(path):
    rng=random.Random(71101);pending=False;value=0;acc=0;lines=[];accepted=completed=stalls=resets=0
    def tick(reset,valid,first,last,rr,q,p,mask):
        nonlocal pending,value,acc,accepted,completed,stalls,resets
        ready=not pending or rr;prev=pending;old=value
        if reset:pending=False;value=acc=0;resets+=1
        else:
            if prev and rr:completed+=1
            if rr:pending=False
            if valid and ready:
                accepted+=1
                # independent integer oracle: number active minus twice mismatches
                acc=(0 if first else acc)+mask.bit_count()-2*((q^p)&mask).bit_count()
                if last:value=acc;pending=True
            elif valid:stalls+=1
        lines.append(f'{int(reset)} {int(valid)} {int(first)} {int(last)} {int(rr)} {q:016x} {p:016x} {mask:016x} {int(ready)} {int(prev)} {old&0xffffffff:08x} {int(pending)} {value&0xffffffff:08x}')
        return ready
    def send(q,p,mask,first,last):
        while True:
            rr=rng.choice((False,False,True));ready=tick(False,True,first,last,rr,q,p,mask)
            if ready:break
    allbits=(1<<64)-1
    tick(True,False,False,False,False,0,0,0)
    # Reset mid-packet: next packet must start from zero.
    send(0,0,allbits,True,False);tick(True,False,False,False,False,0,0,0)
    for d in [1,7,63,64,65,127,256,512,1024,2048,4097,65536,65536]+[rng.randint(1,8192) for _ in range(45)]:
        n=(d+63)//64
        for k in range(n):
            mask=allbits if k<n-1 or d%64==0 else (1<<(d%64))-1
            a=rng.getrandbits(64);b=rng.getrandbits(64)
            # deterministic max and min full scores, and arbitrary masks in short packets
            if d==65536:b=a if completed%2 else a^allbits
            if d<64:mask &= rng.getrandbits(64)
            send(a,b,mask,k==0,k==n-1)
        if rng.randrange(2):
            for _ in range(3):tick(False,False,False,False,False,0,0,0)
    tick(False,False,False,False,True,0,0,0)
    data=('\n'.join(lines)+'\n').encode();Path(path).write_bytes(data)
    return dict(cycles=len(lines),accepted_input_beats=accepted,retired_results=completed,blocked_input_cycles=stalls,resets=resets,vector_sha256=hashlib.sha256(data).hexdigest())


def run(out,oracle_only=False):
    out=Path(out);out.mkdir(parents=True,exist_ok=True);v=out/'f-rtl-vectors.txt';meta=vectors(v);meta['rtl_simulated']=False
    if not oracle_only:
        iv=shutil.which('iverilog');vvp=shutil.which('vvp')
        if not iv or not vvp:raise RuntimeError('Icarus Verilog and vvp required')
        with tempfile.TemporaryDirectory() as td:
            binary=Path(td)/'score.vvp';cmd=[iv,'-g2012','-s','score64_tb','-o',str(binary),str(ROOT/'hardware/hdc/score64.sv'),str(ROOT/'hardware/hdc/score64_tb.sv')]
            with (out/'f-rtl-compile.log').open('wb') as log:subprocess.run(cmd,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=60)
            r=subprocess.run([vvp,str(binary),f'+vectors={v.resolve()}'],capture_output=True,text=True,check=True,timeout=90)
            (out/'f-rtl-run.log').write_text(r.stdout+r.stderr,encoding='utf8');assert f"PASS score64 {meta['cycles']} cycles" in r.stdout
            meta.update(rtl_simulated=True,simulator=subprocess.check_output([iv,'-V'],text=True,stderr=subprocess.STDOUT).splitlines()[0])
    (out/'f-rtl-result.json').write_text(json.dumps(meta,indent=2)+'\n',encoding='utf8');return meta

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--out',required=True);p.add_argument('--oracle-only',action='store_true');a=p.parse_args();print(run(a.out,a.oracle_only))
