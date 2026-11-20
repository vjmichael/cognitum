"""One-shot bounded research worker; no host grant, filesystem input or registry."""
import json,sys
from cognitum.mel import tensor_field as f
MAX_INPUT=4*((f.MAX_FRAME+2)//3)+4*((f.MAX_REQUEST+2)//3)+128

def serve(raw):
    f.need(type(raw) is bytes and 0<len(raw)<=MAX_INPUT,'envelope budget')
    try:d=json.loads(raw)
    except (RecursionError,UnicodeError) as e:raise ValueError('invalid request envelope') from e
    f.need(type(d) is dict and set(d)=={'checkpoint','request'} and f.canonical(d)==raw,'canonical envelope')
    cp,req=f.uncarrier(d['checkpoint']),f.uncarrier(d['request'])
    return f.execute(cp,req)

def main():
    try:
        raw=sys.stdin.buffer.read(MAX_INPUT+1)
        result=serve(raw)
    except (ValueError,TypeError,OverflowError,RecursionError):
        return 2
    sys.stdout.buffer.write(result);return 0

if __name__=='__main__':raise SystemExit(main())
