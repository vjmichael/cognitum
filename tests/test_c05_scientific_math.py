"""C05 six isolated typed math specialists: trustworthy *component* tests only."""
from fractions import Fraction
import unittest

from cognitum.proto import specialists_pb2 as pb
from cognitum.scientific_math import (
    run_inert_specialist, decode_specialist_result, _wire, _polynomial,
    _poly_text,
)

def invoke(kind, request):
    result=run_inert_specialist(kind,_wire(request))
    return decode_specialist_result(kind,result)

class C05SpecialistTests(unittest.TestCase):
    def test_symbolic_polynomial_expansion_and_derivatives(self):
        p=invoke("symbolic",pb.SymbolicRequest(
            expression="(x+1)*(x+2)",action="expand"))
        self.assertEqual(p.polynomial,"x**2 + 3*x + 2")
        self.assertEqual(p.assurance,"exact_symbolic")
        self.assertIn("intent_not_verified",p.limitations)
        d=invoke("symbolic",pb.SymbolicRequest(
            expression="x**3 + 2*x - 7",action="derivative"))
        self.assertEqual(d.polynomial,"3*x**2 + 2")
        self.assertEqual(invoke("symbolic",pb.SymbolicRequest(
            expression="(x-1)*(x+1)",action="expand")).polynomial,"x**2 - 1")
        self.assertEqual(invoke("symbolic",pb.SymbolicRequest(
            expression="1/2*x + 1/3*x",action="expand")).polynomial,"5/6*x")

    def test_symbolic_ast_rejects_unsafe_or_unbounded_forms(self):
        for expression in (
            "sin(x)","x.__class__","__import__('os')","x**100",
            "x/x", "x**7", "y+1","x[0]","x//2", "x%2",
            "1e3","x\n+1", "𝑥+1", "x**-1","x**(1/2)",
            "x"*161, "(x+1)"*70,
        ):
            with self.subTest(expression=expression[:20]),self.assertRaises(ValueError):
                invoke("symbolic",pb.SymbolicRequest(expression=expression,
                                                    action="expand"))
        with self.assertRaises(ValueError):
            invoke("symbolic",pb.SymbolicRequest(expression="x",action="factor"))

    def test_scientific_functions_respect_precision_and_real_domain(self):
        for function,argument,leading in (
            ("sin","0","0.0"),("cos","0","1.0"),("exp","0","1.0"),
            ("log","1","0.0"),("sqrt","4","2.0"),
        ):
            with self.subTest(function=function):
                r=invoke("scientific",pb.ScientificRequest(
                    function=function,argument=argument,digits=45))
                self.assertEqual(r.method,"mpmath")
                self.assertEqual(r.digits,45)
                self.assertIn("approximation_not_exact",r.limitations)
                self.assertAlmostEqual(float(r.decimal),float(leading),places=13)
        sqrt=invoke("scientific",pb.ScientificRequest(
            function="sqrt",argument="2",digits=60))
        self.assertTrue(sqrt.decimal.startswith("1.4142135623730950488"))

    def test_scientific_rejects_nonfinite_unsafe_unbounded(self):
        for function,argument,digits in (
            ("log","0",40),("sqrt","-1",40),("sin","nan",40),
            ("cos","__import__('os')",40),("tan","1",40),
            ("sin","0",10),("exp","1",81),("exp","1e100",40),
            ("sqrt","0."+"0"*70,40),
            ("exp","99"*20,40),
            ("sin","1000",40),
        ):
            with self.subTest(function=function,argument=argument[:10]):
                with self.assertRaises(ValueError):
                    invoke("scientific",pb.ScientificRequest(
                        function=function,argument=argument,digits=digits))

    def test_arbitrary_precision_decimal_math(self):
        add=invoke("precision",pb.PrecisionRequest(
            action="add",left="0.1",right="0.2",digits=50))
        self.assertEqual(add.decimal,"0.3")
        self.assertEqual(add.method,"decimal")
        div=invoke("precision",pb.PrecisionRequest(
            action="divide",left="1",right="3",digits=60))
        self.assertEqual(len(div.decimal.split(".")[1]),60)
        sqrt=invoke("precision",pb.PrecisionRequest(
            action="sqrt",left="2",digits=60))
        self.assertTrue(sqrt.decimal.startswith("1.4142135623730950488"))
        self.assertIn("rounding_may_apply",sqrt.limitations)
        high=invoke("precision",pb.PrecisionRequest(
            action="divide",left="1",right="7",digits=200))
        self.assertEqual(high.digits,200)
        self.assertEqual(len(high.decimal.split(".")[1]),200)

    def test_precision_fail_closed(self):
        for action,a,b,digits in (
            ("divide","1","0",40),("sqrt","-1","",40),
            ("sqrt","4","99",40),("log","1","",40),
            ("add","1","2",0),("add","1","2",257),
            ("divide","NaN","1",40),("add","1","1e999",40),
        ):
            with self.subTest(action=action,a=a):
                with self.assertRaises(ValueError):
                    invoke("precision",pb.PrecisionRequest(
                        action=action,left=a,right=b,digits=digits))

    def test_exact_linear_algebra_determinant_solve_multiply(self):
        a=pb.LinearRequest(action="determinant")
        a.a.add(entries=["1","2"])
        a.a.add(entries=["3","4"])
        self.assertEqual(invoke("linear",a).scalar,"-2")
        b=pb.LinearRequest(action="solve")
        b.a.add(entries=["2","1"])
        b.a.add(entries=["1","3"])
        b.b.add(entries=["1"])
        b.b.add(entries=["2"])
        solved=invoke("linear",b)
        self.assertEqual([list(row.entries) for row in solved.rows],
                         [["1/5"],["3/5"]])
        m=pb.LinearRequest(action="multiply")
        m.a.add(entries=["1","2"])
        m.a.add(entries=["3","4"])
        m.b.add(entries=["1","0"])
        m.b.add(entries=["0","1"])
        self.assertEqual([list(row.entries) for row in invoke("linear",m).rows],
                         [["1","2"],["3","4"]])

    def test_linear_bounds_singular_and_dimensional_errors(self):
        for action,a,b in (
            ("solve",[["1","2"],["2","4"]],[["1"],["2"]]),
            ("determinant",[["1","2"]],[]),
            ("multiply",[["1","2"]],[["1"]]),
            ("determinant",[["1","2"],["3","4"]],[["1"]]),
            ("multiply",[["NaN"]],[["1"]]),
            ("multiply",[["1"]]*5,[["1"]]),
        ):
            q=pb.LinearRequest(action=action)
            for row in a:q.a.add(entries=row)
            for row in b:q.b.add(entries=row)
            with self.subTest(action=action,a=a),self.assertRaises(ValueError):
                invoke("linear",q)

    def test_bisection_returns_exact_root_bracket_without_claiming_full_solver(self):
        q=pb.RootRequest(polynomial="x**2-2",lower="1",upper="2",iterations=50)
        r=invoke("root",q)
        lo,hi=Fraction(r.lower),Fraction(r.upper)
        self.assertLess(lo*lo,Fraction(2))
        self.assertGreater(hi*hi,Fraction(2))
        self.assertLessEqual(hi-lo,Fraction(1,2**50))
        self.assertIn("not_general_equation_solver",r.limitations)
        exact=invoke("root",pb.RootRequest(
            polynomial="x-1",lower="0",upper="2",iterations=5))
        self.assertEqual((exact.lower,exact.upper),("1","1"))

    def test_root_rejects_unbracketed_or_unbounded(self):
        for poly,lo,hi,steps in (
            ("x**2+1","-1","1",40),
            ("x","1","2",40),
            ("x**2-2","2","1",40),
            ("sin(x)","0","1",40),
            ("x**2-2","1","2",129),
        ):
            with self.subTest(poly=poly,lo=lo,hi=hi,steps=steps):
                with self.assertRaises(ValueError):
                    invoke("root",pb.RootRequest(
                        polynomial=poly,lower=lo,upper=hi,iterations=steps))

    def test_bounded_harmonic_oscillator_discrete_simulation(self):
        r=invoke("simulation",pb.SimulationRequest(
            position="1",velocity="0",omega_squared="1",
            step="1/10",steps=20))
        self.assertEqual(r.initial_energy,"1/2")
        self.assertLess(abs(Fraction(r.final_energy)-Fraction(r.initial_energy)),
                        Fraction(1,10))
        self.assertIn("numerical_discretization_error_unbounded",r.limitations)
        self.assertIn("units_and_physical_assumptions_unverified",r.limitations)

    def test_simulation_rejects_unsafe_domains_and_runaway_limits(self):
        for x,v,k,dt,steps in (
            ("1","0","1","0",10),("1","0","1","2",10),
            ("1","0","100","1",10),("1","0","-1","1/10",10),
            ("1","0","1","1/10",257),("1","0","1","1/10",0),
            ("1","0","1","1e999",10),
        ):
            with self.subTest(k=k,dt=dt,steps=steps),self.assertRaises(ValueError):
                invoke("simulation",pb.SimulationRequest(
                    position=x,velocity=v,omega_squared=k,step=dt,steps=steps))

    def test_all_six_domains_have_distinct_native_protobuf_messages(self):
        names=("Symbolic","Scientific","Precision","Linear","Root","Simulation")
        for name in names:
            self.assertIn(name+"Request",pb.DESCRIPTOR.message_types_by_name)
            self.assertIn(name+"Result",pb.DESCRIPTOR.message_types_by_name)
        self.assertEqual(pb.DESCRIPTOR.package,"cognitum.math.v1")
        self.assertEqual(len(pb.DESCRIPTOR.message_types_by_name),15)

    def test_domain_wire_rejects_duplicates_unknown_and_cross_domain(self):
        request=pb.SymbolicRequest(expression="x+1",action="expand")
        wire=_wire(request)
        for data in (wire+b"\x0a\x01x",wire+b"\x98\x06\x01",
                     b"",b"\x0a\xff",b"x"*4097):
            with self.subTest(frame=data[:10]),self.assertRaises(ValueError):
                run_inert_specialist("symbolic",data)
        result=run_inert_specialist("symbolic",wire)
        with self.assertRaises(ValueError):
            decode_specialist_result("symbolic",result+b"\x98\x06\x01")
        with self.assertRaises(ValueError):
            run_inert_specialist("garbage",wire)

    def test_model_discovery_is_protobuf_only_inert_and_strict(self):
        from cognitum.math_catalog import encode_catalog,decode_catalog,CATALOG_TYPE_URL
        raw=encode_catalog()
        self.assertNotEqual(raw[:1],b"{")
        cat=decode_catalog(raw)
        self.assertEqual(cat.schema_version,1)
        self.assertFalse(cat.host_approved)
        self.assertEqual(len(cat.specialists),6)
        for entry in cat.specialists:
            self.assertFalse(entry.registered)
            self.assertFalse(entry.model_advertised)
            self.assertTrue(entry.use_when)
            self.assertTrue(entry.avoid_when)
            self.assertTrue(entry.input_type_url.startswith("type.googleapis.com/cognitum.math.v1."))
        self.assertEqual(CATALOG_TYPE_URL,"type.googleapis.com/cognitum.math.v1.SpecialistCatalog")
        forged=pb.SpecialistCatalog()
        forged.CopyFrom(cat)
        forged.specialists[0].registered=True
        with self.assertRaises(ValueError):
            decode_catalog(forged.SerializeToString(deterministic=True))
        forged.CopyFrom(cat)
        forged.host_approved=True
        with self.assertRaises(ValueError):
            decode_catalog(forged.SerializeToString(deterministic=True))
        for bad in (raw+b"\x98\x06\x01",raw+b"\x08\x01",
                    b"",b"\x0a\xff",b"x"*8193):
            with self.subTest(frame=bad[:12]),self.assertRaises(ValueError):
                decode_catalog(bad)

    def test_no_ce_registration_grant_or_worker_gate_bypass(self):
        from cognitum.plugins.calculator import Calculator
        from cognitum.worker_wire import admission_status,start_isolated_worker
        self.assertEqual([op.name for op in Calculator().manifest().operations],
                         ["calc.rational"])
        self.assertFalse(admission_status().admitted)
        with self.assertRaises(PermissionError):
            start_isolated_worker(scientific_math=True,grants="all")
        self.assertNotIn("grants",[f.name for f in pb.SymbolicRequest.DESCRIPTOR.fields])


if __name__=="__main__":
    unittest.main()
