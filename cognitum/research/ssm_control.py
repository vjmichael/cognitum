"""Bounded discrete linear control research, offline simulation only."""
import numpy as np
from fractions import Fraction
from scipy.linalg import solve_discrete_are
from scipy.signal import place_poles
from scipy.optimize import minimize, linprog, nnls
from .ssm_stochastic import need, array, square, cov, receipt, gaussian_update


def plant(A,B):
    A=square(A);B=array(B,2);n=len(A);need(B.shape[0]==n and B.shape[1]<=16,'plant shape');return A,B


def vector(x,n):
    x=array(x,1);need(x.shape==(n,),'vector shape');return x


def horizon(h):
    need(type(h) is int and 1<=h<=64,'horizon budget');return h


def cost(A,B,Q,R):
    A,B=plant(A,B);return A,B,cov(Q,len(A)),cov(R,B.shape[1],True)


def bounded(x):
    need(np.isfinite(x).all() and np.max(abs(x))<=1e8,'state/solution budget');return x


def rank_full(M,n):
    v=np.linalg.svd(M,compute_uv=False);need(len(v)>=n and v[n-1]>1e-10*v[0] and v[0]>0,'rank deficient')


def placement(A,B,poles):
    A,B=plant(A,B);n=len(A);p=vector(poles,n);need(np.all(abs(p)<1) and len(set(p))==n,'distinct real stable poles required')
    rank_full(np.column_stack([np.linalg.matrix_power(A,j)@B for j in range(n)]),n)
    K=bounded(place_poles(A,B,p,rtol=1e-8,maxiter=100).gain_matrix);e=np.linalg.eigvals(A-B@K);need(np.max(abs(np.sort_complex(e)-np.sort_complex(p)))<=1e-6,'pole residual');return receipt(gain=K,poles=e)


def observer(A,C,poles,x0,estimate,inputs,B):
    A,B=plant(A,B);C=array(C,2);n=len(A);need(C.shape[1]==n and C.shape[0]<=16,'sensor shape');x=vector(x0,n);z=vector(estimate,n);U=array(inputs,2);horizon(len(U));need(U.shape[1]==B.shape[1],'input shape');L=placement(A.T,C.T,poles)['gain'].T;X=[x];Z=[z]
    for u in U:
        z=bounded(A@z+B@u+L@(C@x-C@z));x=bounded(A@x+B@u);X.append(x);Z.append(z)
    E=np.array(X)-np.array(Z);return receipt(gain=L,states=np.array(X),estimates=np.array(Z),errors=E,error_poles=np.linalg.eigvals(A-L@C))


def lqr(A,B,Q,R):
    A,B,Q,R=cost(A,B,Q,R)
    try:P=solve_discrete_are(A,B,Q,R)
    except np.linalg.LinAlgError as e:raise ValueError('Riccati solution unavailable') from e
    P=(P+P.T)/2;K=bounded(np.linalg.solve(R+B.T@P@B,B.T@P@A));F=A-B@K;res=P-Q-K.T@R@K-F.T@P@F;err=float(np.linalg.norm(res)/max(1,np.linalg.norm(P)));need(err<=1e-8 and np.linalg.eigvalsh(P)[0]>=-1e-10 and np.max(abs(np.linalg.eigvals(F)))<1-1e-8,'stabilizing Riccati witness failed');return receipt(gain=K,value=P,closed_loop=F,residual=err)


def finite_lqr(A,B,Q,R,terminal,x0,steps):
    A,B,Q,R=cost(A,B,Q,R);n=len(A);P=cov(terminal,n);x=vector(x0,n);horizon(steps);g=[];values=[P]
    for _ in range(steps):
        K=np.linalg.solve(R+B.T@P@B,B.T@P@A);F=A-B@K;P=Q+K.T@R@K+F.T@P@F;g.append(K);values.append(P)
    X=[x];U=[];total=0.
    for K in g[::-1]:
        u=bounded(-K@x);total+=x@Q@x+u@R@u;x=bounded(A@x+B@u);X.append(x);U.append(u)
    total+=x@values[0]@x;pred=float(X[0]@values[-1]@X[0]);need(abs(total-pred)<=1e-8*max(1,abs(pred)),'Bellman cost disagreement');return receipt(gains=np.array(g[::-1]),states=np.array(X),inputs=np.array(U),cost=float(total),value=pred)


def lqg(A,B,C,Q,R,W,V,x0,estimate,steps,seed):
    """Discrete stationary predictor feedback, y_t=C x_t+v_t, u_t=-K z_t."""
    A,B,Q,R=cost(A,B,Q,R);n=len(A);C=array(C,2);k=len(C);need(C.shape==(k,n) and k<=16,'sensor shape');W=cov(W,n);V=cov(V,k,True);horizon(steps);need(type(seed) is int and 0<=seed<2**32,'seed');K=lqr(A,B,Q,R)['gain'];P=lqr(A.T,C.T,W,V)['value'];L=np.linalg.solve(V+C@P@C.T,C@P@A.T).T;F=A-B@K;E=A-L@C;Z=np.block([[F,B@K],[np.zeros_like(A),E]]);need(np.max(abs(np.linalg.eigvals(Z)))<1-1e-8,'separation stability');x=vector(x0,n);z=vector(estimate,n);rng=np.random.default_rng(seed);X=[x];H=[z];U=[]
    for _ in range(steps):
        u=-K@z;y=C@x+rng.multivariate_normal(np.zeros(k),V);z=bounded(A@z+B@u+L@(y-C@z));x=bounded(A@x+B@u+rng.multivariate_normal(np.zeros(n),W));X.append(x);H.append(z);U.append(u)
    return receipt(states=np.array(X),estimates=np.array(H),inputs=np.array(U),control_gain=K,observer_gain=L,augmented=Z,poles=np.linalg.eigvals(Z))


def mpc(A,B,Q,R,terminal,x0,steps,x_bound,u_bound):
    """Condensed strictly convex finite-horizon QP; symmetric per-axis boxes."""
    A,B,Q,R=cost(A,B,Q,R);n,m=B.shape;horizon(steps);need(steps*m<=64 and steps*n<=128,'QP budget');P=cov(terminal,n);x=vector(x0,n);xb=vector(x_bound,n);ub=vector(u_bound,m);need(np.all(xb>0) and np.all(ub>0) and np.all(abs(x)<=xb),'initial state/box invalid');S=np.zeros((steps*n,steps*m));D=[]
    for i in range(steps):
        D.append(np.linalg.matrix_power(A,i+1)@x)
        for j in range(i+1):S[i*n:(i+1)*n,j*m:(j+1)*m]=np.linalg.matrix_power(A,i-j)@B
    d=bounded(np.concatenate(D));Qbar=np.kron(np.eye(steps),Q);Qbar[-n:,-n:]=P;Rbar=np.kron(np.eye(steps),R);H=2*(S.T@Qbar@S+Rbar);f=2*S.T@Qbar@d;I=np.eye(steps*m);G=np.vstack((S,-S,I,-I));b=np.r_[np.tile(xb,steps)-d,np.tile(xb,steps)+d,np.tile(ub,steps),np.tile(ub,steps)];need(np.linalg.cond(H)<=1e10,'QP condition')
    u=np.linalg.solve(H,-f)
    if np.max(G@u-b)>1e-9:
        lp=linprog(np.zeros(len(u)),A_ub=G,b_ub=b,bounds=[(None,None)]*len(u),method='highs');need(lp.success,'no feasible plan established');sol=minimize(lambda z:.5*z@H@z+f@z,lp.x,jac=lambda z:H@z+f,constraints={'type':'ineq','fun':lambda z:b-G@z,'jac':lambda z:-G},method='SLSQP',options={'ftol':1e-11,'maxiter':300});need(sol.success,'QP solver failed');u=sol.x
    slack=b-G@u;grad=H@u+f;active=slack<=1e-6;lam=np.zeros(len(b))
    if active.any():lam[active]=nnls(G[active].T,-grad,maxiter=1000)[0]
    primal=float(max(0,-slack.min()));station=float(np.linalg.norm(grad+G.T@lam,np.inf)/max(1,np.linalg.norm(grad,np.inf)));comp=float(np.max(abs(lam*slack))/max(1,np.max(lam)));need(primal<=1e-7 and station<=1e-6 and comp<=1e-6,'KKT residual failed');X=np.vstack((x,(d+S@u).reshape(steps,n)));U=u.reshape(steps,m);total=float(x@Q@x+(d+S@u)@Qbar@(d+S@u)+u@Rbar@u);return receipt(states=bounded(X),inputs=bounded(U),cost=total,primal_residual=primal,stationarity_residual=station,complementarity_residual=comp)


def box_witness(A,B,K,state_bound,input_bound,disturbance):
    """Exact rational sufficient invariant-box and input-box certificate, not synthesis."""
    def rat(x):
        need(type(x) in (int,str,Fraction) and len(str(x))<=48,'rational input');z=Fraction(x);need(z.numerator.bit_length()<=64 and z.denominator.bit_length()<=64,'rational budget');return z
    def mat(a,r,c):
        need(type(a) in (list,tuple) and len(a)==r and all(type(t) in (list,tuple) and len(t)==c for t in a),'matrix shape');return [[rat(x) for x in t] for t in a]
    n=len(A);m=len(K);need(1<=n<=8 and 1<=m<=8,'exact dimension');A,B,K=mat(A,n,n),mat(B,n,m),mat(K,m,n);x=mat([state_bound],1,n)[0];u=mat([input_bound],1,m)[0];w=mat([disturbance],1,n)[0];need(all(t>0 for t in x+u) and all(t>=0 for t in w),'box bounds');F=[[A[i][j]-sum(B[i][k]*K[k][j] for k in range(m)) for j in range(n)] for i in range(n)];sx=[x[i]-w[i]-sum(abs(F[i][j])*x[j] for j in range(n)) for i in range(n)];su=[u[i]-sum(abs(K[i][j])*x[j] for j in range(n)) for i in range(m)];need(all(t>=0 for t in sx+su),'box witness rejected');return dict(state_margin=tuple(map(str,sx)),input_margin=tuple(map(str,su)),exact_rational_box_verified=True,execution_authorized=False)
