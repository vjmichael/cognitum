"""P46R5 exact ordering tests with real fixed Protobuf worker and MOCK scope.

Unlike live cgroup2, this intentionally cannot certify OS containment.
It checks code-level host/watchkeeper ordering and fail-closed behavior.
"""
from __future__ import annotations
import os
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import patch

from cognitum import cgroup2_fixed_runner as runner
from cognitum.alpha_native import make_call
from cognitum.host_surviving_watchkeeper import WatchkeeperDenied
from cognitum.cgroup2_contract import ContainmentUnavailable


class MockScope:
    events = []
    def __init__(self, root):
        self.path = None
        self._members = set()
    def create(self):
        self.events.append('scope-created')
        self.path = Path('/tmp/mock-p46r5-scope-unusable')
    def attach_before_release(self, pid):
        self.events.append('worker-attached')
        self._members.add(pid)
    def members(self):
        return set(self._members)
    def kill_and_verify_empty(self, timeout=5):
        self.events.append('scope-emergency-cleanup')
        return True
    def remove_empty(self):
        self.events.append('scope-removed')
        self.path = None


class MockWatchkeeper:
    def __init__(self):
        self.jobid = 'd'*32
        self.receipt_path = Path('/tmp/mock-p46r5-evidence.json')
        self.closed = False
        self.proc = type('MockWatchProc', (), {'poll': lambda _: None})()
    def close_lease(self):
        self.closed = True
        MockScope.events.append('lease-closed')
    def await_cleanup(self, **kwargs):
        self.close_lease()
        MockScope.events.append('watchkeeper-observed-clean')
        return {'status':'KERNEL_TREE_CLEARED', 'TEST_ONLY_NO_KERNEL':True}


class HandoffOrderTests(unittest.TestCase):
    def setUp(self):
        MockScope.events = []

    def test_mock_handoff_real_fixed_worker_requires_watchkeeper_before_spawn(self):
        original_spawn = runner.subprocess.Popen
        def watchdog_arm(path, **kwargs):
            MockScope.events.append('watchkeeper-armed')
            return MockWatchkeeper()
        def spawn(*args, **kwargs):
            self.assertIn('watchkeeper-armed', MockScope.events)
            self.assertNotIn('worker-attached', MockScope.events)
            MockScope.events.append('worker-spawned')
            return original_spawn(*args, **kwargs)
        call=make_call('p46r5','1/3 + 1/6')
        frame=struct.pack('>I',len(call))+call
        with patch.object(runner,'FixtureCgroupScope',MockScope), \
             patch.object(runner,'arm_watchkeeper',side_effect=watchdog_arm), \
             patch.object(runner.subprocess,'Popen',side_effect=spawn):
            result=runner.execute_fixed_in_cgroup(frame)
        self.assertEqual(result['status'],'FIXED_FIXTURE_OBSERVED')
        self.assertFalse(result['production_sandbox_verified'])
        self.assertFalse(result['untrusted_worker_authorized'])
        self.assertTrue(result['host_surviving_cleanup_observed'])
        self.assertLess(MockScope.events.index('scope-created'), MockScope.events.index('watchkeeper-armed'))
        self.assertLess(MockScope.events.index('watchkeeper-armed'), MockScope.events.index('worker-spawned'))
        self.assertLess(MockScope.events.index('worker-spawned'), MockScope.events.index('worker-attached'))
        self.assertLess(MockScope.events.index('worker-attached'), MockScope.events.index('watchkeeper-observed-clean'))

    def test_watchkeeper_death_after_arming_denies_worker_release(self):
        class DiedBeforeRelease(MockWatchkeeper):
            def __init__(self):
                super().__init__()
                self.proc = type('DeadWatchProc', (), {'poll': lambda _: 7})()
            def await_cleanup(self, **kwargs):
                self.close_lease()
                raise WatchkeeperDenied('WATCHER_DIED')
        call=make_call('p46r5','1/3 + 1/6')
        frame=struct.pack('>I',len(call))+call
        with patch.object(runner,'FixtureCgroupScope',MockScope), \
             patch.object(runner,'arm_watchkeeper',return_value=DiedBeforeRelease()):
            with self.assertRaisesRegex(ContainmentUnavailable,'WATCHKEEPER_EXITED_BEFORE_WORKER_RELEASE'):
                runner.execute_fixed_in_cgroup(frame)
        self.assertIn('scope-emergency-cleanup',MockScope.events)
        self.assertNotIn('watchkeeper-observed-clean',MockScope.events)

    def test_watchkeeper_arm_failure_means_no_worker_started(self):
        with patch.object(runner,'FixtureCgroupScope',MockScope), \
             patch.object(runner,'arm_watchkeeper',side_effect=WatchkeeperDenied('NOT_ARMED')), \
             patch.object(runner.subprocess,'Popen') as spawn:
            with self.assertRaisesRegex(WatchkeeperDenied,'NOT_ARMED'):
                runner.execute_fixed_in_cgroup(b'\x00\x00\x00\x00')
            spawn.assert_not_called()
        self.assertEqual(MockScope.events,['scope-created','scope-emergency-cleanup','scope-removed'])

    def test_watchkeeper_denial_falls_back_to_emergency_cleanup_and_never_pass(self):
        class DenyingWatch(MockWatchkeeper):
            def await_cleanup(self, **kwargs):
                self.close_lease()
                raise WatchkeeperDenied('UNOBSERVED')
        call=make_call('p46r5','1/3 + 1/6')
        frame=struct.pack('>I',len(call))+call
        with patch.object(runner,'FixtureCgroupScope',MockScope), \
             patch.object(runner,'arm_watchkeeper',return_value=DenyingWatch()):
            with self.assertRaisesRegex(WatchkeeperDenied,'UNOBSERVED'):
                runner.execute_fixed_in_cgroup(frame)
        self.assertIn('scope-emergency-cleanup',MockScope.events)
        self.assertIn('lease-closed',MockScope.events)


if __name__=='__main__':unittest.main()
