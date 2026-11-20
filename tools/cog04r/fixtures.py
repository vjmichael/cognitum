"""Frozen qualification cases (not inputs to the independent reference)."""
from cognitum.research.kan_sturm_liouville import Problem
CASES={
    'DD':Problem((1,0),(0,0),(1,0),('D',0),('D',0)),
    'NN':Problem((1,0),(0,0),(1,0),('N',0),('N',0)),
    'DN':Problem((1,0),(0,0),(1,0),('D',0),('N',0)),
    'RR':Problem((1,0),(0,0),(1,0),('R',1),('R',2)),
    'variable-DD':Problem((1,1),(0,1),(2,-1),('D',0),('D',0)),
    'variable-NR':Problem((2,-1),(1,-1),(1,1),('N',0),('R',2)),
}
