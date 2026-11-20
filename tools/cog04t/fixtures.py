from cognitum.research.kan_coupled_ritz import Problem
CASES={
    'symmetric':Problem(0,((2,1),(1,2))),
    'triangular':Problem(0,((1,3),(0,3))),
    'complex':Problem(0,((1,-3),(2,1))),
    'drift-complex':Problem(3,((1,-3),(2,1))),
    'drift-real':Problem(-2,((1,3),(0,3))),
}
