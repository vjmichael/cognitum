"""Small research references for Kleyko et al., survey I §§2.3.2/.4/.8/.11.
Not a fixed-width shared tensor format, production index or full optimized VSA.
"""
import numpy as np


def real(a, rank):
    a = np.asarray(a)
    if a.dtype != np.dtype('float64') or a.ndim != rank or a.size == 0 or not np.isfinite(a).all():
        raise ValueError('expected finite float64 operands')
    return a


def tpr_bind(role, filler):
    role, filler = real(role, 1), real(filler, 1)
    if role.size * filler.size > 65536: raise ValueError('tensor budget')
    return np.outer(role, filler)


def tpr_extract(dual_role, composite):
    dual_role, composite = real(dual_role, 1), real(composite, 2)
    if composite.size > 65536 or dual_role.size != composite.shape[0]: raise ValueError('tensor shape/budget')
    return dual_role @ composite


def mbat_bind(role_matrix, filler):
    role_matrix, filler = real(role_matrix, 2), real(filler, 1)
    if role_matrix.size > 65536 or role_matrix.shape[1] != filler.size: raise ValueError('matrix shape/budget')
    return role_matrix @ filler


def mbat_recover(role_matrix, bound):
    role_matrix, bound = real(role_matrix, 2), real(bound, 1)
    m,n = role_matrix.shape
    if role_matrix.size > 65536 or m != bound.size or m < n or np.linalg.matrix_rank(role_matrix) != n:
        raise ValueError('cannot uniquely recover filler')
    if np.linalg.cond(role_matrix) > 1e6: raise ValueError('ill-conditioned role')
    return np.linalg.lstsq(role_matrix,bound,rcond=None)[0]


def sparse_rows(rows):
    rows = np.asarray(rows)
    if rows.dtype != np.bool_ or rows.ndim != 2 or not 1 <= rows.shape[0] <= 4096 or not 1 <= rows.shape[1] <= 65536:
        raise ValueError('invalid binary rows')
    return rows


def sparse_conjunction(rows): return np.all(sparse_rows(rows),axis=0)
def sparse_disjunction(rows): return np.any(sparse_rows(rows),axis=0)


def additive_cdt(rows, permutations):
    """Additive CDT per survey Eq. 12; explicit fixed codebook permutations."""
    z = sparse_disjunction(rows); p = np.asarray(permutations)
    if p.dtype != np.int64 or p.ndim != 2 or p.shape[1] != z.size or not 1 <= len(p) <= 64:
        raise ValueError('invalid permutations')
    for row in p:
        if not np.array_equal(np.sort(row),np.arange(z.size)): raise ValueError('not a bijection')
    return z & np.any(z[p],axis=0)


def geometric_bind(a,b):
    """Euclidean Clifford algebra Cl(n,0), coefficient index = blade bitmask.
    Full multivector result, not projected; bounded n<=8, O(4**n) oracle.
    """
    a,b = real(a,1),real(b,1); d=a.size
    if b.size!=d or d>256 or d & (d-1): raise ValueError('blade dimension must be equal power of two <=256')
    out=np.zeros(d,np.float64)
    for i,x in enumerate(a):
        if x==0: continue
        for j,y in enumerate(b):
            if y==0: continue
            swaps=sum((j & ((1<<k)-1)).bit_count() for k in range(d.bit_length()-1) if i & (1<<k))
            out[i^j] += (-1 if swaps%2 else 1)*x*y
    return out

# Explicit reference conventions for the heterogeneous representations. An
# algebra can support composition without an invertible binding (sparse/CDT).
# We deliberately expose extraction only where a valid inverse/witness exists.
from dataclasses import dataclass

@dataclass(frozen=True)
class SurveySpec:
    family: str
    shape: tuple

    def __post_init__(self):
        ranks = {'TPR': 2, 'MBAT': 1, 'SPARSE_AND_OR': 1, 'CDT': 1, 'GEOMETRIC': 1}
        if (self.family not in ranks or type(self.shape) is not tuple
            or len(self.shape) != ranks[self.family]
            or any(type(x) is not int or not 1 <= x <= 65536 for x in self.shape)
            or int(np.prod(self.shape, dtype=np.int64)) > 65536):
            raise ValueError('invalid survey representation')
        if self.family == 'GEOMETRIC' and (self.shape[0] > 256 or self.shape[0] & (self.shape[0]-1)):
            raise ValueError('invalid blade dimension')

    @property
    def dtype(self):
        return np.dtype(bool if self.family in ('SPARSE_AND_OR','CDT') else np.float64)

    def checked(self, a):
        a = np.asarray(a)
        if a.dtype != self.dtype or a.shape != self.shape or not np.isfinite(a).all():
            raise ValueError('invalid survey operand')
        return a

    def compose(self, a, b, *, permutations=None):
        """Representation-specific composition, never a universal product.

        TPR/MBAT take role then filler; geometric uses ordered blade product.
        Sparse conjunction and CDT are lossy and have no general inverse.
        """
        if self.family != 'CDT' and permutations is not None:
            raise ValueError('permutations only supported for CDT')
        if self.family == 'TPR':
            return self.checked(tpr_bind(a,b))
        if self.family == 'MBAT':
            return self.checked(mbat_bind(a,b))
        a,b = self.checked(a),self.checked(b)
        if self.family == 'SPARSE_AND_OR': return a & b
        if self.family == 'CDT':
            if permutations is None: raise ValueError('CDT requires explicit codebook permutations')
            return self.checked(additive_cdt([a,b],permutations))
        return self.checked(geometric_bind(a,b))

    def recover(self, role, bound, *, side=None):
        bound=self.checked(bound)
        if self.family == 'GEOMETRIC':
            inv=geometric_unit_inverse(self.checked(role))
            if side=='left': return self.checked(geometric_bind(inv,bound))
            if side=='right': return self.checked(geometric_bind(bound,inv))
            raise ValueError('explicit geometric inverse side required')
        if side is not None: raise ValueError('side is only defined for geometric recovery')
        if self.family == 'TPR': return real(tpr_extract(role,bound),1)
        if self.family == 'MBAT': return real(mbat_recover(role,bound),1)
        raise ValueError('lossy sparse composition has no general inverse')

    def bundle(self, rows, *, permutations=None):
        rows = np.asarray(rows)
        if (rows.ndim != len(self.shape)+1 or rows.shape[1:] != self.shape
            or rows.dtype != self.dtype or not 1 <= len(rows) <= 4096
            or rows.size > 8388608 or not np.isfinite(rows).all()):
            raise ValueError('invalid survey bundle/budget')
        if self.family == 'CDT':
            if permutations is None: raise ValueError('CDT requires explicit codebook permutations')
            return self.checked(additive_cdt(rows, permutations))
        if permutations is not None: raise ValueError('permutations only supported for CDT bundling')
        if self.family == 'SPARSE_AND_OR': return np.any(rows, axis=0)
        return self.checked(rows.sum(axis=0))

    def similarity(self, a, b):
        a,b = self.checked(a),self.checked(b)
        if self.dtype == np.dtype(bool):
            # Explicit Jaccard convention; zero union is not evidence.
            union = np.count_nonzero(a | b)
            if not union: raise ValueError('undefined empty support similarity')
            return np.count_nonzero(a & b)/union
        x,y = a.ravel(),b.ravel()
        # Scale first to avoid overflow from squaring finite large operands.
        sa,sb = np.max(np.abs(x)),np.max(np.abs(y))
        if sa == 0 or sb == 0: raise ValueError('undefined zero cosine')
        x,y = x/sa,y/sb
        return float(np.clip(np.dot(x,y)/(np.linalg.norm(x)*np.linalg.norm(y)),-1,1))

    def permute(self, a, shift, *, axis=None):
        a = self.checked(a)
        if type(shift) is not int: raise ValueError('invalid shift')
        if self.family == 'TPR':
            if type(axis) is not int or axis not in (0,1): raise ValueError('TPR axis required')
            return np.roll(a,shift%self.shape[axis],axis=axis)
        if axis is not None: raise ValueError('explicit axis only for TPR')
        if self.family == 'GEOMETRIC':
            # Rotate the *basis generators*, preserving induced blade signs.
            # An arbitrary coefficient rotation would not preserve the product.
            n = self.shape[0].bit_length()-1
            out = np.zeros_like(a)
            if n == 0: return a.copy()
            for i, value in enumerate(a):
                order = [(k+shift)%n for k in range(n) if i & (1<<k)]
                blade = sum(1<<k for k in order)
                sign = (-1)**sum(x>y for j,x in enumerate(order) for y in order[j+1:])
                out[blade] = sign*value
            return out
        return np.roll(a,shift%self.shape[0])

    def cleanup(self, query, bank, *, min_similarity, k=1):
        query,bank = self.checked(query),np.asarray(bank)
        if (bank.ndim != len(self.shape)+1 or bank.shape[1:] != self.shape
            or bank.dtype != self.dtype or not 1 <= len(bank) <= 4096
            or bank.size > 8388608 or not np.isfinite(bank).all()
            or type(k) is not int or not 1 <= k <= len(bank)
            or isinstance(min_similarity,bool) or not np.isfinite(min_similarity)
            or not (-1 <= min_similarity <= 1)):
            raise ValueError('invalid cleanup bank or threshold')
        scores = np.array([self.similarity(query,row) for row in bank])
        ids = np.argsort(-scores,kind='stable')[:k]
        ids = ids[scores[ids]>=min_similarity]
        return ids,scores[ids]


def geometric_reverse(a):
    a = real(a,1)
    if a.size > 256 or a.size & (a.size-1): raise ValueError('invalid blade dimension')
    return a*np.array([(-1)**(i.bit_count()*(i.bit_count()-1)//2) for i in range(a.size)])


def geometric_unit_inverse(a):
    """Inverse restricted to normalized versors; no general multivector inverse."""
    a = real(a,1); r = geometric_reverse(a)
    one = np.zeros_like(a); one[0]=1
    if not (np.allclose(geometric_bind(a,r),one,rtol=0,atol=1e-10)
        and np.allclose(geometric_bind(r,a),one,rtol=0,atol=1e-10)):
        raise ValueError('inverse requires a unit reverse-invertible multivector')
    return r
