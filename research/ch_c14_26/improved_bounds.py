"""CH26 research: directed-MPFR Fisher log-determinant and interval Hessian.

Does not modify CH24. 3 parameter small-box research only.
Proof of determinant envelope: for 0<w_i(β)<=u_i, Fisher(β) ⪯ U=Σ n_i u_i xx^T;
thus det Fisher(β) <= det(U). All arithmetic uses outward-rounded MPFR.
"""
from __future__ import annotations
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'CH_C14_24'))
from verified_bnb import FirthObjective, determinant, midpoint_bounds, interval_box, exact_decimal
from mpfr_interval import Interval as I, MP, UP, DOWN, up_abs

ZERO=I('0'); ONE=I('1'); HALF=I('0.5')

def upper_point(v):
    return I.from_ends(v.hi, v.hi)

def exact_sign_upper(v):
    return I.from_ends(v.hi,v.hi)

def max_upper(a, b):
    return a if a.cmp(b)>=0 else b

def min_upper(a,b):
    return a if a.cmp(b)<=0 else b

def lower_positive(model, w):
    inds,coeff=model.reference_minor
    ref=coeff
    for i in inds: ref=ref*w[i]
    if ref.lo.cmp(MP('0'))<=0: raise ArithmeticError('No proven positive minor')
    return ref.lo

class ImprovedObjective(FirthObjective):
    def __init__(self, data):
        super().__init__(data)
        self.groups_const=[(tuple(I(x) for x in row['x']),row['n'],row['s']) for row in data['rows']]
        self.outer=[[[x[j]*x[k]*n for k in range(self.d)] for j in range(self.d)] for x,n,s in self.groups_const]
        self.tangents=[]
        # Unlike CH24, the Loewner Gram determinant is O(n*d²) and works for >20 groups.

    def set_tangents(self, anchors):
        """Freeze global concave-loglikelihood tangent planes at exact coordinates."""
        self.tangents=[]
        for coords in anchors:
            if len(coords)!=self.d:raise ValueError('Invalid tangent coordinate dimension')
            beta=[I(v) for v in coords]
            val=I('0');gradient=[I('0') for _ in range(self.d)]
            for xx,n,s in self.groups_const:
                eta=sum((xx[j]*beta[j] for j in range(self.d)),I('0'))
                p=ONE/(ONE+(-eta).exp())
                val=val+(eta*s-(ONE+eta.exp()).log()*n)
                for j in range(self.d):gradient[j]=gradient[j]+(s-p*n)*xx[j]
            self.tangents.append((list(coords),val,gradient))

    def _tangent_cap(self,box):
        cap=None
        for coords,val,grads in self.tangents:
            tangent=val
            for j in range(self.d):
                tangent=tangent + grads[j]*(box[j]-I(coords[j]))
            if cap is None or tangent.hi.cmp(cap)<0:cap=tangent.hi
        return cap

    def _weight_and_prob(self, eta):
        # Monotonic logistic p enclosure and endpoint-min unimodal Fisher w.
        p=ONE/(ONE+(-eta).exp())
        w=self._weight_enclosure(eta)
        return p,w

    def _pack(self, box, derivatives=False):
        d=self.d
        group=[]
        ll=I('0'); ll_cap=I('0')
        Ientries=[[I('0') for _ in range(d)] for _ in range(d)]
        Uentries=[[I('0') for _ in range(d)] for _ in range(d)]
        weights=[]
        for i,(xx,n,s) in enumerate(self.groups_const):
            eta=sum((xx[j]*box[j] for j in range(d)),I('0'))
            p,w=self._weight_and_prob(eta);weights.append(w)
            ll=ll+(eta*s-(eta.exp()+ONE).log()*n)
            if s==0:
                e=I.from_ends(eta.lo,eta.lo)
                cap=-(ONE+e.exp()).log()*n
            elif s==n:
                e=I.from_ends(eta.hi,eta.hi)
                cap=e*n-(ONE+e.exp()).log()*n
            else:
                a=I(s)/I(n); b=I(n-s)/I(n)
                cap=I(s)*a.log()+I(n-s)*b.log()
            ll_cap=ll_cap+upper_point(cap)
            wp=upper_point(w)
            for j in range(d):
                for k in range(j,d):
                    c=self.outer[i][j][k]
                    Ientries[j][k]=Ientries[j][k]+w*c
                    Uentries[j][k]=Uentries[j][k]+wp*c
            group.append((eta,p,w))
        for j in range(d):
            for k in range(j):
                Ientries[j][k]=Ientries[k][j];Uentries[j][k]=Uentries[k][j]
        return ll,ll_cap,Ientries,Uentries,weights,group

    def objective(self, box):
        ll,ll_cap,F,U,w,group=self._pack(box)
        detF=determinant(F)
        lower=lower_positive(self,w)
        if detF.lo.cmp(lower)>0: lower=detF.lo
        # Hadamard: det(F) <= Π F_jj; exact Loewner: det(F) <= det(U).
        had=I('1')
        for j in range(self.d):had=had*F[j][j]
        upper=min_upper(detF.hi,had.hi)
        detU=determinant(U)
        # U is exact PSD (even when interval expression cancellation is pessimistic).
        if detU.hi.cmp(MP('0'))<0:raise ArithmeticError('Impossible negative Gram determinant upper')
        upper=min_upper(upper,detU.hi)
        if lower.cmp(upper)>0:raise ArithmeticError('Inconsistent Fisher determinant envelope')
        logdet=I.from_ends(lower,upper).log()
        # Individual concave binomial terms have rigorously bounded scalar maxima.
        ll_upper=min_upper(ll.hi,ll_cap.hi)
        tangent_cap=self._tangent_cap(box)
        if tangent_cap is not None:ll_upper=min_upper(ll_upper,tangent_cap)
        full=I.from_ends(ll.lo,ll_upper)+HALF*logdet
        return full, 'loewner_gram_plus_binomial_envelope'

    def analytic_derivatives(self, box):
        """Interval ∇J and ∇²J using w'=w(1-2p), w''=w((1-2p)^2-2w).

        Uses adj(F)/det(F) and positive Cauchy-Binet lower determinant. No
        second-order Jet composition. Interval products round outwards.
        """
        d=self.d
        ll,cap,F,U,w,group=self._pack(box)
        D=[[[I('0') for k in range(d)] for j in range(d)] for a in range(d)]
        E=[[[[I('0') for k in range(d)] for j in range(d)] for b in range(d)] for a in range(d)]
        gl=[I('0') for _ in range(d)]
        for idx,((xx,n,s),(eta,p,wi)) in enumerate(zip(self.groups_const,group)):
            q=ONE-I(2)*p
            wp=wi*q
            wpp=wi*(q*q-I(2)*wi)
            for a in range(d):
                gl[a]=gl[a]+(s-I(n)*p)*xx[a]
                for j in range(d):
                    for k in range(d):
                        coeff=self.outer[idx][j][k]*xx[a]
                        D[a][j][k]=D[a][j][k]+coeff*wp
                        for b in range(d):
                            E[a][b][j][k]=E[a][b][j][k]+coeff*xx[b]*wpp
        determinant_interval=determinant(F)
        lo=lower_positive(self,w)
        if determinant_interval.lo.cmp(lo)>0:lo=determinant_interval.lo
        had=I('1')
        for j in range(d):had=had*F[j][j]
        hi=min_upper(determinant_interval.hi,had.hi)
        detU=determinant(U)
        hi=min_upper(hi,detU.hi)
        detint=I.from_ends(lo,hi)
        # adjugate(F) / det(F), valid for any positive definite Fisher matrix.
        if d==1: adj=[[I(1)]]
        elif d==2: adj=[[F[1][1],-F[0][1]],[-F[1][0],F[0][0]]]
        else:
            adj=[[F[1][1]*F[2][2]-F[1][2]*F[2][1], F[0][2]*F[2][1]-F[0][1]*F[2][2],F[0][1]*F[1][2]-F[0][2]*F[1][1]],
                 [F[1][2]*F[2][0]-F[1][0]*F[2][2], F[0][0]*F[2][2]-F[0][2]*F[2][0],F[0][2]*F[1][0]-F[0][0]*F[1][2]],
                 [F[1][0]*F[2][1]-F[1][1]*F[2][0], F[0][1]*F[2][0]-F[0][0]*F[2][1],F[0][0]*F[1][1]-F[0][1]*F[1][0]]]
        inv=[[adj[j][k]/detint for k in range(d)] for j in range(d)]
        # A_a = inv * dF_a. H = -F + .5(tr(inv*d2F_ab)-tr(A_b A_a)).
        A=[[[sum((inv[j][m]*D[a][m][k] for m in range(d)),I(0)) for k in range(d)] for j in range(d)] for a in range(d)]
        g=[];h=[]
        for a in range(d):
            g.append(gl[a]+HALF*sum((A[a][j][j] for j in range(d)),I(0)))
        for a in range(d):
            hr=[]
            for b in range(d):
                tr1=sum((inv[j][k]*E[a][b][k][j] for j in range(d) for k in range(d)),I('0'))
                tr2=sum((A[a][j][k]*A[b][k][j] for j in range(d) for k in range(d)),I('0'))
                hr.append(-F[a][b]+HALF*(tr1-tr2))
            h.append(hr)
        return g,h
