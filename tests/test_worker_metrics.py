import os
import sys
import time
import unittest
from cognitum import worker
from cognitum.worker_metrics import observe_one


class Fixture:
    def handle(self,operation,payload):
        if operation=='slow':time.sleep(5)
        if operation=='invalid':raise ValueError('invalid')
        if operation=='exit':os._exit(3)
        # Force a modest process-local memory and CPU workload.
        data=bytearray(4*1024*1024)
        for i in range(0,len(data),4096):data[i]=1
        return {'sum':sum(data),'answer':payload.get('answer',0)}


@unittest.skipUnless(sys.platform.startswith('linux') or sys.platform=='win32','native observer platform')
class MetricsTests(unittest.TestCase):
    def test_exact_worker_and_result(self):
        expected=worker.execute(Fixture,'calc',{'answer':9},5000)
        actual,m=observe_one(lambda:worker.execute(Fixture,'calc',{'answer':9},5000))
        self.assertEqual(expected,actual)
        self.assertEqual(actual,('ok',{'sum':1024,'answer':9}))
        self.assertEqual(m['status'],'measured')
        self.assertEqual(m['observed_workers'],1)
        self.assertGreater(m['peak_resident_bytes_observed'],0)
        self.assertGreaterEqual(m['cpu_seconds'],0)
        self.assertIs(m['cpu_final'],sys.platform=='win32')
        self.assertIsNone(sys.getprofile())

    def test_refusal_timeout_and_exit_unchanged(self):
        for op,timeout,status in [('invalid',5000,'invalid_input'),('slow',100,'timed_out'),('exit',5000,'error')]:
            with self.subTest(op=op):
                result,m=observe_one(lambda:worker.execute(Fixture,op,{},timeout))
                self.assertEqual(result,(status,None))
                self.assertEqual(m['observed_workers'],1)
                self.assertIsNone(sys.getprofile())

    def test_no_worker_and_existing_profiler(self):
        value,m=observe_one(lambda:42)
        self.assertEqual(value,42);self.assertEqual(m['status'],'unavailable')
        hook=lambda *args:None
        sys.setprofile(hook)
        try:
            with self.assertRaises(ValueError):observe_one(lambda:42)
            self.assertIs(sys.getprofile(),hook)
        finally:sys.setprofile(None)

    def test_exception_restores_profiler(self):
        def fail():raise RuntimeError('fixture')
        with self.assertRaisesRegex(RuntimeError,'fixture'):observe_one(fail)
        self.assertIsNone(sys.getprofile())


if __name__=='__main__':unittest.main()
