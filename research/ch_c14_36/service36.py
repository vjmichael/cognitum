"""CH36 Linux research: bounded parallel independent proof replay, serial signed commit.

The untrusted journal writer may only name a frozen original case. Every
verification executes in a signer-owned *separate process*, under the signer
UID. No journal-supplied path, proof, digest or signature reaches the signer.
A single critical section serializes signature publication, tip advancement,
and duplicate checks after each mathematical replay.
"""
from __future__ import annotations
import argparse, concurrent.futures, json, multiprocessing, socketserver, threading
from pathlib import Path
from service35 import WitnessService, Request
from trust35 import canonical, verify_chain, witness_original_ch33, atomic

class ParallelWitnessService(socketserver.ThreadingMixIn, WitnessService):
    daemon_threads = True
    request_queue_size = 32

    def __init__(self, socket_path, *, store, source_root, journals_root, allowed_uid, workers=3):
        if type(workers) is not int or workers < 1 or workers > 4:
            raise ValueError('Workers must be in [1,4]')
        self.commit_lock = threading.Lock()
        self.verification_slots = threading.BoundedSemaphore(workers)
        self.pool = None
        try:
            super().__init__(socket_path, store=store, source_root=source_root,
                             journals_root=journals_root, allowed_uid=allowed_uid)
            self.pool = concurrent.futures.ProcessPoolExecutor(
                max_workers=workers, mp_context=multiprocessing.get_context('spawn'))
        except BaseException:
            if self.pool is not None: self.pool.shutdown(cancel_futures=True)
            raise

    def handle_message(self, msg, uid):
        if self.allowed_uid is None or uid != self.allowed_uid:
            raise PermissionError('Only the configured journal writer UID is admitted')
        if type(msg) is not dict or set(msg) != {'op', 'case_id'} or msg['op'] != 'verify':
            raise ValueError('Only a frozen case ID is accepted')
        case = msg['case_id']
        if type(case) is not str or case not in self.pins:
            raise ValueError('Case is not in immutable signer policy')
        with self.verification_slots:
            # A fresh child process performs every independent 224-bit MPFR replay.
            # Attestations do not come from the journal's AF_UNIX request.
            att = self.pool.submit(witness_original_ch33, case,
                                   self.source_root, self.journals_root, self.pins).result(timeout=900)
        # The original source is sealed from the writer; nevertheless recheck
        # the independent pin before publication and serialize all writes.
        if att['case_id'] != case or att['scientific_release'] != 'NO_GO' or not att['proof_replayed']:
            raise ValueError('Independent proof worker returned unexpected scope')
        with self.commit_lock:
            tip = self.trusted_tip()
            current = verify_chain(self.store.root, self.public,
                                   expected_fingerprint=self.fingerprint, expected_tip=tip)
            if case in current['cases']:
                raise ValueError('Original case already witnessed')
            result = self.store.publish(att, expected_tip=tip)
            atomic(self.store.root, 'trusted_tip.json',
                   canonical({'tip': result['tip'], 'fingerprint': self.fingerprint}) + b'\n',
                   prefix='tip')
        return {'status': 'SIGNED_AFTER_INDEPENDENT_MPFR_REPLAY',
                'case_id': case, 'tip_sha256': result['tip'], 'record': result['record'],
                'public_key_fingerprint_sha256': self.fingerprint, 'scientific_release': 'NO_GO'}

    def server_close(self):
        try:
            if self.pool is not None: self.pool.shutdown(wait=True, cancel_futures=True)
        finally: super().server_close()

if __name__ == '__main__':
    p = argparse.ArgumentParser()
    for f in ('socket','store','source','journals'):
        p.add_argument('--'+f, required=True)
    p.add_argument('--allowed-uid', type=int, required=True)
    p.add_argument('--workers', type=int, default=3)
    a = p.parse_args()
    srv = ParallelWitnessService(a.socket,store=a.store,source_root=a.source,
                                 journals_root=a.journals,allowed_uid=a.allowed_uid,
                                 workers=a.workers)
    try: srv.serve_forever(poll_interval=.2)
    except KeyboardInterrupt: pass
    finally: srv.server_close()
