from cognitum.research.kan_tensor_ritz import Problem
from tools.cog04r.fixtures import CASES
from fractions import Fraction as Q
CASES={
    'square-DD':Problem((CASES['DD'],)*2,(1,1)),
    'box-DD':Problem((CASES['DD'],)*3,(1,1,1)),
    'rectangle-variable':Problem((CASES['variable-DD'],CASES['variable-NR']),(1,Q(3,2))),
    'box-mixed':Problem((CASES['NN'],CASES['DN'],CASES['variable-NR']),(1,2,Q(3,2))),
    'box-NN':Problem((CASES['NN'],)*3,(1,1,1)),
}
