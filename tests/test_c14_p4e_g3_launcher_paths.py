"""Pin-safe virtualenv launch paths for older causal worker adapters.

No OS containment or Lu authentication is claimed by this source-level suite.
"""
from dataclasses import replace
from pathlib import Path
import sys
import unittest

from cognitum.causal_dowhy_backend import run_dowhy_frame
from cognitum.causal_mature_backend import run_mature_frame
from cognitum.proto import causal_dowhy_pb2 as dw, causal_mature_pb2 as m
from tests.test_c14_dowhy_adapter import make_request as dowhy_req, policy as dowhy_policy
from tests.test_c14_p3c_mature_adapter import fixtures, policy as mature_policy, encode


class TestG3LauncherPaths(unittest.TestCase):
    def test_dowhy_relative_executable_denied(self):
        request=dowhy_req(homogenous=True).SerializeToString(deterministic=True)
        got=dw.DoWhyResult.FromString(run_dowhy_frame(
            request,host_authorized=True,enabled=True,
            worker_policy=replace(dowhy_policy(),python_executable='python')))
        self.assertEqual(got.reason_code,'WORKER_EXECUTABLE_PATH_INVALID')
        self.assertFalse(got.estimated_ate)

    def test_mature_relative_executable_denied(self):
        req=fixtures()[0]; got=m.MatureCausalResult.FromString(run_mature_frame(
            encode(req),host_authorized=True,enabled=True,
            worker_policy=replace(mature_policy(req.backend),python_executable='python')))
        self.assertEqual(got.reason_code,'WORKER_EXECUTABLE_PATH_INVALID')
        self.assertFalse(got.effects)

    def test_dowhy_parent_traversal_path_denied(self):
        request=dowhy_req(homogenous=True).SerializeToString(deterministic=True)
        bad=str(Path(sys.executable).parent / '..' / 'bin' / 'python')
        got=dw.DoWhyResult.FromString(run_dowhy_frame(
            request,host_authorized=True,enabled=True,
            worker_policy=replace(dowhy_policy(),python_executable=bad)))
        self.assertEqual(got.reason_code,'WORKER_EXECUTABLE_PATH_INVALID')

    def test_mature_parent_traversal_path_denied(self):
        req=fixtures()[1]
        bad=str(Path(sys.executable).parent / '..' / 'bin' / 'python')
        got=m.MatureCausalResult.FromString(run_mature_frame(
            encode(req),host_authorized=True,enabled=True,
            worker_policy=replace(mature_policy(req.backend),python_executable=bad)))
        self.assertEqual(got.reason_code,'WORKER_EXECUTABLE_PATH_INVALID')

if __name__=='__main__':unittest.main()
