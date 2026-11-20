"""Bounded offline linear control extensions; no actuator interfaces."""
import itertools
from fractions import Fraction
import numpy as np
from scipy.optimize import linprog, minimize, nnls
from scipy.stats import norm
from .ssm_control import plant, vector, horizon, cost, bounded, rank_full, placement, mpc
from .ssm_stochastic import need, array, cov, receipt


def unknown_input(A,B,C,E,poles,x0,estimate,inputs,disturbances):
    """Full-order discrete UIO, noiseless measurements, full-rank CE."""
    A,B=plant(A,B);n=len(A);C,E=array(C,2),array(E,2);k=C.shape[0];d=E.shape[1]
    need(C.shape[1]==n and E.shape[0]==n and k<=16 and d<=n,'UIO shape');rank_full(C@E,d)
    H=E@np.linalg.pinv(C@E);T=np.eye(n)-H@C;need(np.linalg.norm(T@E,np.inf)<=1e-9*max(1,np.linalg.norm(E,np.inf)),'decoupling residual')
    L=placement((T@A).T,C.T,poles)['gain'].T;F=T@A-L@C;K=L+F@H
    x=vector(x0,n);z=vector(estimate,n)-H@C@x;U,W=array(inputs,2),array(disturbances,2);horizon(len(U));need(U.shape[1]==B.shape[1] and W.shape==(len(U),d),'sequence shape')
    X=[x];Z=[z+H@C@x]
    for u,w in zip(U,W):
        z=bounded(F@z+T@B@u+K@C@x);x=bounded(A@x+B@u+E@w);X.append(x);Z.append(z+H@C@x)
    err=np.array(X)-np.array(Z);need(np.max(abs(err[1:]-err[:-1]@F.T))<=1e-7*max(1,np.max(abs(err))),'error identity')
    return receipt(states=np.array(X),estimates=np.array(Z),errors=err,error_transition=F,decoupling=H)


def prediction(A,B,x,h):
    n,m=B.shape;S=np.zeros((h*n,h*m));D=[]
    for i in range(h):
        D.append(np.linalg.matrix_power(A,i+1)@x)
        for j in range(i+1):S[i*n:(i+1)*n,j*m:(j+1)*m]=np.linalg.matrix_power(A,i-j)@B
    return bounded(np.concatenate(D)),bounded(S)


def plan(d,S,Q,R,P,x,limits,ub):
    h,n=limits.shape;m=len(ub);need(h*n<=128 and h*m<=64 and S.shape==(h*n,h*m) and np.all(limits>=0) and np.all(ub>0),'plan budget/tightening infeasible')
    D=np.kron(np.eye(h),Q);D[-n:,-n:]=P;M=np.kron(np.eye(h),R);H=2*(S.T@D@S+M);f=2*S.T@D@d;I=np.eye(h*m);G=np.vstack((S,-S,I,-I));b=np.r_[limits.ravel()-d,limits.ravel()+d,np.tile(ub,h),np.tile(ub,h)]
    need(np.linalg.cond(H)<=1e10,'QP condition');u=np.linalg.solve(H,-f)
    if np.max(G@u-b)>1e-9:
        lp=linprog(np.zeros(len(u)),A_ub=G,b_ub=b,bounds=[(None,None)]*len(u),method='highs');need(lp.success,'no feasible plan established')
        ans=minimize(lambda v:.5*v@H@v+f@v,lp.x,jac=lambda v:H@v+f,constraints={'type':'ineq','fun':lambda v:b-G@v,'jac':lambda v:-G},method='SLSQP',options={'ftol':1e-11,'maxiter':300});need(ans.success,'QP solve failed');u=ans.x
    slack=b-G@u;g=H@u+f;active=slack<=1e-6;lam=np.zeros(len(b))
    if active.any():lam[active]=nnls(G[active].T,-g,maxiter=1000)[0]
    primal=max(0.,float(-slack.min()));station=float(np.max(abs(g+G.T@lam))/max(1,np.max(abs(g))));comp=float(np.max(abs(lam*slack))/max(1,np.max(lam)));need(primal<=1e-7 and station<=1e-6 and comp<=1e-6,'KKT residual failed')
    z=bounded(d+S@u);return receipt(states=np.vstack((x,z.reshape(h,n))),inputs=bounded(u.reshape(h,m)),cost=float(x@Q@x+z@D@z+u@M@u),primal_residual=primal,stationarity_residual=station,complementarity_residual=comp)


def uncertain_plan(A,B,Q,R,P,x,h,xb,ub,*,disturbance=None,noise_cov=None,risk=None):
    """Open-loop robust box or iid additive Gaussian joint chance via union bound."""
    A,B,Q,R=cost(A,B,Q,R);n,m=B.shape;horizon(h);need(h*n<=128 and h*m<=64,'plan budget');P=cov(P,n);x,xb,ub=vector(x,n),vector(xb,n),vector(ub,m);need(np.all(xb>0) and np.all(abs(x)<=xb),'initial box');need((disturbance is None)!=(noise_cov is None),'select one uncertainty model')
    margin=[];v=np.zeros(n)
    if disturbance is not None:
        w=vector(disturbance,n);need(np.all(w>=0) and risk is None,'disturbance profile')
        for _ in range(h):v=bounded(abs(A)@v+w);margin.append(v)
    else:
        W=cov(noise_cov,n);need(type(risk) in (int,float) and .0001<=risk<=.5,'risk');q=norm.isf(risk/(2*h*n));V=np.zeros((n,n))
        for _ in range(h):V=bounded(A@V@A.T+W);margin.append(q*np.sqrt(np.maximum(0,np.diag(V))))
    margin=np.array(margin);d,S=prediction(A,B,x,h);z=plan(d,S,Q,R,P,x,xb-margin,ub);z.update(tightening=margin,joint_risk_bound=risk,recursive_feasibility_established=False);return z


def receding(A,B,Q,R,P,x,h,xb,ub,disturbances,disturbance_bound):
    A,B=plant(A,B);n=len(A);x=vector(x,n);w=vector(disturbance_bound,n);W=array(disturbances,2);horizon(len(W));need(W.shape[1]==n and np.all(abs(W)<=w),'simulation disturbance outside model');X=[x];U=[]
    for a in W:
        z=uncertain_plan(A,B,Q,R,P,x,h,xb,ub,disturbance=w);u=z['inputs'][0];x=bounded(A@x+B@u+a);need(np.all(abs(x)<=np.asarray(xb)+1e-7),'simulated state violation');X.append(x);U.append(u)
    return receipt(states=np.array(X),inputs=np.array(U),recursive_feasibility_established=False)


def adaptive(A,B,Q,R,P,x,h,xb,ub,X,U,Y,disturbances):
    """Offline certainty-equivalent receding simulation with expanding least squares."""
    A,B=plant(A,B);n,m=B.shape;X,U,Y,W=(array(v,2) for v in (X,U,Y,disturbances));horizon(len(W));need(X.shape==Y.shape and X.shape[1]==n and U.shape==(len(X),m) and W.shape[1]==n and len(X)<=4096,'adaptive shape');x=vector(x,n);D=np.column_stack((X,U));rank_full(D,n+m);states=[x];actions=[];models=[]
    for w in W:
        rank_full(D,n+m);theta=np.linalg.lstsq(D,Y,rcond=None)[0].T;models.append(theta);z=mpc(theta[:,:n],theta[:,n:],Q,R,P,x,h,xb,ub);u=z['inputs'][0];v=bounded(A@x+B@u+w);need(np.all(abs(v)<=np.asarray(xb)),'simulated state violation');D=np.vstack((D,np.r_[x,u]));Y=np.vstack((Y,v));x=v;states.append(x);actions.append(u)
    return receipt(states=np.array(states),inputs=np.array(actions),models=np.array(models),robustness_established=False)


def data_plan(states,inputs,Q,R,P,x,h,xb,ub):
    """Direct trajectory-span prediction from fully observed, noiseless LTI data.
    Require full row rank of [initial state; stacked controls], and consistency.
    """
    X,U=array(states,2),array(inputs,2);n,m=X.shape[1],U.shape[1];horizon(h);need(len(X)==len(U)+1 and h*n<=128 and h*m<=64 and n<=16 and m<=16 and h<=len(U)<=4096,'trajectory budget');Q,P=cov(Q,n),cov(P,n);R=cov(R,m,True);x,xb,ub=vector(x,n),vector(xb,n),vector(ub,m);need(np.all(xb>0) and np.all(abs(x)<=xb),'initial box')
    cols=len(U)-h+1;D=np.column_stack([np.r_[X[i],U[i:i+h].ravel()] for i in range(cols)]);Y=np.column_stack([X[i+1:i+h+1].ravel() for i in range(cols)]);rank_full(D,n+h*m);M=np.linalg.lstsq(D.T,Y.T,rcond=None)[0].T;err=float(np.max(abs(M@D-Y)));need(err<=1e-8*max(1,np.max(abs(Y))),'inconsistent/noisy trajectory span')
    z=plan(M[:,:n]@x,M[:,n:],Q,R,P,x,np.tile(xb,(h,1)),ub);z.update(span_residual=err,noiseless_model_assumption=True);return z


def experiment_design(candidates,choose,prior,noise):
    """Finite D-optimal subset; rows are known linear sensitivity vectors."""
    X=array(candidates,2);k,n=X.shape;need(1<=n<=16 and k<=16 and type(choose) is int and 1<=choose<=k,'design budget');P=cov(prior,n);v=vector(noise,k);need(np.all(v>0),'noise variance');best=None
    for ids in itertools.combinations(range(k),choose):
        D=X[list(ids)]/np.sqrt(v[list(ids),None]);I=P+D.T@D;sign,l=np.linalg.slogdet(I)
        if np.linalg.eigvalsh(I)[0]<=1e-10*max(1,np.linalg.norm(I,2)) or sign<=0:continue
        if best is None or l>best[0]:best=(float(l),ids,I)
    need(best is not None,'no full rank information');l,ids,I=best;return receipt(indices=ids,information=I,logdet=l,local_linear_model_only=True)


def sensor_design(A,candidates,choose,steps,noise):
    A=np.asarray(A);A,_=plant(A,np.ones((len(A),1)));X=array(candidates,2);k,n=X.shape;horizon(steps);need(n==len(A) and k<=16 and type(choose) is int and 1<=choose<=k,'sensor shape');v=vector(noise,k);need(np.all(v>0),'noise variance');blocks=[]
    for i in range(k):
        D=np.array([X[i]@np.linalg.matrix_power(A,j) for j in range(steps)])/np.sqrt(v[i]);blocks.append(D.T@D)
    best=None
    for ids in itertools.combinations(range(k),choose):
        G=sum(blocks[i] for i in ids);s,l=np.linalg.slogdet(G)
        if s>0 and np.linalg.eigvalsh(G)[0]>1e-10*max(1,np.linalg.norm(G,2)) and (best is None or l>best[0]):best=(float(l),ids,G)
    need(best is not None,'no observable sensor subset');l,ids,G=best;return receipt(indices=ids,gramian=G,logdet=l)


def scalar_safety(a,b,x,proposed,xb,ub,w):
    """Exact rational nearest safe input, one-step robust box, scalar plant."""
    def rat(v):
        need(type(v) in (int,str,Fraction) and len(str(v))<=48,'rational input');q=Fraction(v);need(q.numerator.bit_length()<=64 and q.denominator.bit_length()<=64,'rational budget');return q
    a,b,x,u,xb,ub,w=map(rat,(a,b,x,proposed,xb,ub,w));need(xb>0 and ub>0 and 0<=w<=xb and abs(x)<=xb,'unsafe initial/bounds');r=xb-w;lo,hi=-ub,ub
    if b:
        p,q=sorted(((-r-a*x)/b,(r-a*x)/b));lo=max(lo,p);hi=min(hi,q)
    else:need(abs(a*x)<=r,'no safe input')
    need(lo<=hi,'no safe input');v=min(hi,max(lo,u));margin=xb-abs(a*x+b*v)-w;need(margin>=0 and abs(v)<=ub,'witness failure');return dict(input=str(v),interval=(str(lo),str(hi)),state_margin=str(margin),input_margin=str(ub-abs(v)),exact_rational_one_step_verified=True,execution_authorized=False)
