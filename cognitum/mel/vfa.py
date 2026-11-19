"""Explicit research plugin using the original Registry/Runtime/Worker path.
No install, enable, nomination, or host grants occur on import.
"""
import numpy as np
from cognitum.contracts import Manifest,Operation,Shape
from cognitum.research.vfa_multivariate import Mixture
from .objects import MathObject,MAX_WIRE,pair,result_object,validate_result,need

NAME='mel_vfa_reference'
VERSION='1.0.0'
OPERATIONS=('vfa.evaluate','vfa.gradient')
INPUT=Shape((('function',MAX_WIRE),('points',MAX_WIRE)))
OUTPUT=Shape((('object',8192),))


class VFAPlugin:
    def manifest(self):
        return Manifest(NAME,VERSION,tuple(Operation(op,op,INPUT,OUTPUT,assurance='numerical') for op in OPERATIONS),track='research')

    def health(self):return True

    def self_test(self):
        from .objects import gaussian,points
        f=gaussian([[0]],[[1]],[2],constant=1,axes=[('x','1')],domain=[(-2,2)],output_unit='1')
        p=points(f,[[0]])
        return MathObject(self.handle('vfa.evaluate',request_payload(f,p))['object']).values==(3.,)

    def handle(self,operation,request):
        need(operation in OPERATIONS,'unsupported operation');INPUT.validate(request)
        f,p=MathObject(request['function']),MathObject(request['points'])
        _,fm,v,_,pm,x=pair(f,p);t,d=fm['shape'];n=pm['shape'][0]
        mixture=Mixture(np.array(v[1:1+t*d]).reshape(t,d),np.array(v[1+2*t*d:]),np.array(v[1+t*d:1+2*t*d]).reshape(t,d),v[0])
        coordinates=np.array(x).reshape(n,d)
        y=mixture.evaluate(coordinates) if operation=='vfa.evaluate' else mixture.gradient(coordinates)
        obj=result_object(operation,f,p,y.ravel().tolist())
        out={'object':obj.wire};OUTPUT.validate(out);return out


def request_payload(function,coordinates):
    pair(function,coordinates)
    return {'function':function.wire,'points':coordinates.wire}


def checked_response(response,operation,function,coordinates,*,request_id,correlation_id):
    """Validate lineage and semantic metadata; not an independent value proof."""
    need(response.execution_status=='completed' and response.operation==operation and response.request_id==request_id and response.correlation_id==correlation_id and response.module=={'name':NAME,'version':VERSION} and response.assurance=='numerical','wrong or unsuccessful response')
    OUTPUT.validate(response.result)
    return validate_result(operation,function,coordinates,MathObject(response.result['object']))
