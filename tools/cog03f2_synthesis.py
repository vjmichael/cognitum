"""F2 pilot: real Icarus differential gate and XC7 Yosys mapping.
No hardware programming; no timing signoff from generic mapped cells.
"""
import argparse, hashlib, json, re, shutil, subprocess, tempfile
from collections import Counter
from pathlib import Path
from tools.cog03f_rtl import vectors
ROOT=Path(__file__).resolve().parents[1]
TOPS=('score64','score64_balanced','score64_compact')

def digest(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def balanced_count(value):
    if not 0<=value<1<<64:raise ValueError('uint64 only')
    levels=[(value>>i)&1 for i in range(64)]
    while len(levels)>1:levels=[levels[i]+levels[i+1] for i in range(0,len(levels),2)]
    return levels[0]

def cell_counts(netlist,top):
    if top not in TOPS:raise ValueError('unknown top')
    modules=netlist['modules'];m=modules[top]
    counts=Counter(c['type'].lstrip('\\') for c in m['cells'].values())
    if not counts or any(k.startswith('$') for k in counts):raise ValueError('generic/unmapped cells')
    for k in counts:
        # No arbitrary module/blackbox accepted as a primitive. Scope: arithmetic lane only.
        if not re.fullmatch(r'LUT[1-6]|LUT6_2|FD(?:RE|SE|CE|PE)(?:_1)?|CARRY4|MUXF[78]|INV|BUF|BUFG|VCC|GND|DSP48E1|RAMB(?:18|36)E1|SRL16E|SRLC32E',k):
            raise ValueError('unexpected mapped type '+k)
    lut=sum(n for k,n in counts.items() if k.startswith('LUT'))
    ff=sum(n for k,n in counts.items() if k.startswith('FD'))
    if not lut or not ff:raise ValueError('missing mapped arithmetic')
    return dict(cells=dict(sorted(counts.items())),lut=lut,ff=ff,carry4=counts['CARRY4'],dsp=counts['DSP48E1'],bram36=counts['RAMB36E1'],bram18=counts['RAMB18E1'])

def executable(name):
    p=shutil.which(name)
    if not p:raise RuntimeError(f'{name} is required; no synthetic result substitution')
    return p

def checked(cmd,log,timeout):
    with Path(log).open('wb') as f:subprocess.run(cmd,cwd=ROOT,stdout=f,stderr=subprocess.STDOUT,check=True,timeout=timeout)

def primitive_library(yosys):
    candidates=[Path(yosys).resolve().parent.parent/'share/yosys/xilinx/cells_sim.v',Path('/usr/share/yosys/xilinx/cells_sim.v'),Path('/usr/local/share/yosys/xilinx/cells_sim.v')]
    config=shutil.which('yosys-config')
    if config:candidates.insert(0,Path(subprocess.check_output([config,'--datdir'],text=True).strip())/'xilinx/cells_sim.v')
    for p in candidates:
        if p.is_file():return p
    raise RuntimeError('Yosys XC7 simulation models unavailable')

def run(out):
    out=Path(out).resolve();out.mkdir(parents=True,exist_ok=True)
    iv,vvp,yosys=(executable(k) for k in ('iverilog','vvp','yosys'))
    cells=primitive_library(yosys)
    oracle=out/'f2-vectors.txt';meta=vectors(oracle);rows=[]
    source_tb=ROOT/'hardware/hdc/score64_tb.sv'
    with tempfile.TemporaryDirectory(prefix='cog-f2-') as td:
        for top in TOPS:
            src=ROOT/f'hardware/hdc/{top}.sv'
            tb=Path(td)/f'{top}_tb.sv';text=source_tb.read_text(encoding='utf8');assert text.count('score64 dut(.*);')==1
            tb.write_text(text.replace('score64 dut(.*);',f'{top} dut(.*);').replace('cycle=cycle+1;', 'cycle=cycle+1; if(cycle%256==0) begin $display("progress %0d",cycle); $fflush(); end'),encoding='utf8')
            binary=Path(td)/f'{top}.vvp'
            checked([iv,'-g2012','-s','score64_tb','-o',str(binary),str(src),str(tb)],out/f'{top}-compile.log',60)
            sim=out/f'{top}-sim.log';checked([vvp,str(binary),f'+vectors={oracle}'],sim,120)
            if f"PASS score64 {meta['cycles']} cycles" not in sim.read_text():raise ValueError('missing simulation pass')
            mapped=Path(td)/f'{top}.json'
            # No external path interpolated into a Yosys command: source is repo-relative and generated output path is fixed in private temp dir.
            work=Path(td)/top;work.mkdir();shutil.copyfile(src,work/'design.sv')
            synlog=out/f'{top}-yosys.log'
            with synlog.open('wb') as f:subprocess.run([yosys,'-p',f'read_verilog -sv design.sv; synth_xilinx -family xc7 -top {top} -noiopad; check -assert; write_json mapped.json; write_verilog -noattr mapped.v; stat'],cwd=work,stdout=f,stderr=subprocess.STDOUT,check=True,timeout=300)
            mapped=work/'mapped.json';net=json.loads(mapped.read_text());row=cell_counts(net,top)
            dst=out/f'{top}-mapped.json';shutil.copyfile(mapped,dst)
            verilog=out/f'{top}-mapped.v';shutil.copyfile(work/'mapped.v',verilog)
            row.update(top=top,source_sha256=digest(src),simulated=True,cycles=meta['cycles'],netlist_sha256=digest(dst),sim_sha256=digest(sim),synthesis_log_sha256=digest(synlog),mapped_verilog_sha256=digest(verilog),mapped_simulated=False)
            rows.append(row)
            # Preserve measured resource counts before expensive simulation; never mark a partial receipt accepted.
            (out/'f2-mapping-partial.json').write_text(json.dumps(dict(complete=False,rows=rows,timing_qualified=False),indent=2)+'\n',encoding='utf8')
        # Map all variants before simulation; a slow baseline must not hide other mapped counts.
        failures=[]
        for row in rows:
            top=row['top'];tb=Path(td)/f'{top}_tb.sv';verilog=out/f'{top}-mapped.v'
            gate_binary=Path(td)/f'{top}-mapped.vvp';gate_compile=out/f'{top}-mapped-compile.log';gate_sim=out/f'{top}-mapped-sim.log'
            gate_sim.unlink(missing_ok=True)
            try:
                checked([iv,'-g2012','-s','score64_tb','-o',str(gate_binary),str(cells),str(verilog),str(tb)],gate_compile,120)
                gate_sim.touch()
                checked([vvp,str(gate_binary),f'+vectors={oracle}'],gate_sim,900)
                if f"PASS score64 {meta['cycles']} cycles" not in gate_sim.read_text():raise ValueError('missing mapped simulation pass')
                row.update(mapped_simulated=True,mapped_sim_sha256=digest(gate_sim))
            except (subprocess.TimeoutExpired, subprocess.CalledProcessError, ValueError) as e:
                row.update(mapped_simulated=False,mapped_sim_error=str(e),mapped_sim_sha256=digest(gate_sim) if gate_sim.exists() else None)
                failures.append(top)
            (out/'f2-mapping-partial.json').write_text(json.dumps(dict(complete=False,rows=rows,timing_qualified=False),indent=2)+'\n',encoding='utf8')
        if failures:raise RuntimeError('mapped simulation failed: '+','.join(failures))
    receipt=dict(scope='XC7 generic mapped netlist only, no part-specific placement/routing/timing/board measurements',yosys=subprocess.check_output([yosys,'-V'],text=True).strip(),iverilog=subprocess.check_output([iv,'-V'],text=True,stderr=subprocess.STDOUT).splitlines()[0],primitive_model_sha256=digest(cells),vectors=meta,rows=rows,timing_qualified=False,physical_verified=False)
    (out/'f2-synthesis.json').write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf8');return receipt

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--out',required=True);a=p.parse_args();print(run(a.out))
