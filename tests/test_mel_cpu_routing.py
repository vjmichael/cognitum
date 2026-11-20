import unittest
from dataclasses import replace

try:
    import numpy
    from google.protobuf import message
except ModuleNotFoundError:
    raise unittest.SkipTest('optional scientific dependencies absent')

from cognitum.mel import admission as a, native as n, engines as e
from cognitum.mel import cpu_routing as c
from cognitum.registry import Registry


class CpuRouteTests(unittest.TestCase):
    def setUp(self):
        self.registry=Registry()
        self.registry.install(n.NativeVFAPlugin,enabled=True)
        self.registry.install(e.EnginePlugin,enabled=True)
        for route in a.routes(include_engines=True):
            self.registry.nominate(route.operation,n.NAME if route.operation in n.OP else e.NAME)

    def test_all_reviewed_cpu_routes_are_inert(self):
        for route in a.routes(include_engines=True):
            for preference in ('auto','cpu'):
                s=c.select_cpu(self.registry,route,preference=preference,allow_research=True)
                self.assertEqual(s.backend,'cpu')
                self.assertEqual(s.descriptor_sha256,route.descriptor_sha256)
                self.assertFalse(s.execution_authorized)

    def test_strict_non_cpu_refusal(self):
        route=a.routes()[0]
        for backend in ('vulkan','gpu','fpga','cuda','rocm','distributed',None,True):
            with self.subTest(backend=backend):
                with self.assertRaises(ValueError):
                    c.select_cpu(self.registry,route,preference=backend,allow_research=True)

    def test_default_off_stale_and_unavailable(self):
        route=a.routes()[0]
        with self.assertRaises(ValueError):c.select_cpu(self.registry,route)
        with self.assertRaises(ValueError):
            c.select_cpu(self.registry,replace(route,descriptor_sha256='0'*64),allow_research=True)
        self.registry.enable(n.NAME,False)
        with self.assertRaises(ValueError):c.select_cpu(self.registry,route,allow_research=True)

    def test_nominated_factory_cannot_be_substituted(self):
        class Impostor(n.NativeVFAPlugin):pass
        self.registry.install(Impostor,enabled=True)
        with self.assertRaises(ValueError):
            c.select_cpu(self.registry,a.routes()[0],allow_research=True)


if __name__=='__main__':unittest.main()
