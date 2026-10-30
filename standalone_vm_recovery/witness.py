"""Operator-controlled, OFF-GUEST SQLite high-water witness for VM rollback tests.

A rollback-resistant *test fixture* only while the database is hosted outside the
VM and neither the VM nor its test credentials can modify it. The host operator
alone executes this CLI; no HTTP endpoint or guest-side write capability exists.
No TPM, independent signing service, or production authority is claimed.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import sys

class WitnessRejected(Exception): pass

def _valid(m):
    if not isinstance(m,dict) or m.get('schema')!=1 or m.get('research_only') is not True:
        raise WitnessRejected('INVALID_WITNESS_REQUEST')
    for key in ('scope','anchor_sha256'):
        if not isinstance(m.get(key),str) or not m[key] or len(m[key])>256:
            raise WitnessRejected('INVALID_WITNESS_'+key.upper())
    if len(m['anchor_sha256'])!=64:
        raise WitnessRejected('INVALID_SHA256')
    try: bytes.fromhex(m['anchor_sha256'])
    except ValueError as ex:raise WitnessRejected('INVALID_SHA256') from ex
    if type(m.get('sequence')) is not int or not 0<=m['sequence']<=100_000:
        raise WitnessRejected('INVALID_SEQUENCE')
    if type(m.get('epoch')) is not int or not 1<=m['epoch']<=1_000_000:
        raise WitnessRejected('INVALID_EPOCH')
    return m

def open_db(path):
    path=Path(path)
    if not path.parent.is_dir():raise WitnessRejected('WITNESS_PARENT_MISSING')
    conn=sqlite3.connect(path,timeout=15,isolation_level=None)
    conn.execute('PRAGMA synchronous=FULL')
    conn.execute('PRAGMA journal_mode=DELETE')
    conn.execute('CREATE TABLE IF NOT EXISTS highwater (scope TEXT NOT NULL PRIMARY KEY, epoch INTEGER NOT NULL, sequence INTEGER NOT NULL, digest TEXT NOT NULL)')
    conn.execute('CREATE TABLE IF NOT EXISTS history (scope TEXT NOT NULL, epoch INTEGER NOT NULL, sequence INTEGER NOT NULL, digest TEXT NOT NULL, previous_digest TEXT, PRIMARY KEY(scope,epoch,sequence))')
    return conn

def _transaction(conn,fn):
    conn.execute('BEGIN IMMEDIATE')
    try:
        r=fn()
        conn.execute('COMMIT')
        return r
    except BaseException:
        conn.execute('ROLLBACK');raise

def register(conn,manifest):
    m=_valid(manifest)
    if m['sequence']!=0:raise WitnessRejected('ENROLLMENT_MUST_BE_GENESIS')
    def op():
        if conn.execute('SELECT 1 FROM highwater WHERE scope=?',(m['scope'],)).fetchone():
            raise WitnessRejected('SCOPE_ALREADY_REGISTERED')
        vals=(m['scope'],m['epoch'],m['sequence'],m['anchor_sha256'])
        conn.execute('INSERT INTO highwater VALUES (?,?,?,?)',vals)
        conn.execute('INSERT INTO history VALUES (?,?,?,?,NULL)',vals)
        return {'status':'ENROLLED','scope':m['scope'],'sequence':0}
    return _transaction(conn,op)

def advance(conn,manifest):
    m=_valid(manifest)
    prev=m.get('previous_anchor_sha256')
    if not isinstance(prev,str) or len(prev)!=64:raise WitnessRejected('MISSING_PREVIOUS_ANCHOR')
    def op():
        row=conn.execute('SELECT epoch, sequence, digest FROM highwater WHERE scope=?',(m['scope'],)).fetchone()
        if not row:raise WitnessRejected('NOT_ENROLLED')
        epoch,sequence,digest=row
        if epoch!=m['epoch']:raise WitnessRejected('EPOCH_CHANGE_REQUIRES_OPERATOR_PROTOCOL')
        if sequence+1 != m['sequence'] or digest!=prev:
            raise WitnessRejected('STALE_OR_FORKED_UPDATE')
        if digest==m['anchor_sha256']:raise WitnessRejected('UNCHANGED_ANCHOR')
        conn.execute('UPDATE highwater SET sequence=?,digest=? WHERE scope=?',(m['sequence'],m['anchor_sha256'],m['scope']))
        conn.execute('INSERT INTO history VALUES (?,?,?,?,?)',(m['scope'],m['epoch'],m['sequence'],m['anchor_sha256'],prev))
        return {'status':'COMMITTED','scope':m['scope'],'sequence':m['sequence']}
    return _transaction(conn,op)

def check(conn,manifest):
    m=_valid(manifest)
    row=conn.execute('SELECT epoch,sequence,digest FROM highwater WHERE scope=?',(m['scope'],)).fetchone()
    if row is None:return {'status':'NOT_ENROLLED','pass':False}
    epoch,sequence,digest=row
    if epoch!=m['epoch']:result='EPOCH_MISMATCH'
    elif m['sequence']<sequence:result='ROLLBACK_DETECTED'
    elif m['sequence']>sequence:result='UNWITNESSED_AHEAD'
    elif m['anchor_sha256']!=digest:result='FORK_OR_TAMPER_DETECTED'
    else:result='MATCH'
    return {'status':result,'pass':result=='MATCH','highwater_sequence':sequence,'reported_sequence':m['sequence']}

def main(argv=None):
    p=argparse.ArgumentParser(description='HOST-ONLY independent high-water test witness; never store database in the guest VM')
    p.add_argument('command',choices=['enroll','advance','check'])
    p.add_argument('--db',required=True)
    p.add_argument('--request',required=True)
    args=p.parse_args(argv)
    try:
        manifest=json.loads(Path(args.request).read_text('utf8'))
        conn=open_db(args.db)
        with conn:
            result={'enroll':register,'advance':advance,'check':check}[args.command](conn,manifest)
        print(json.dumps(result,indent=2))
        if result.get('pass') is False:return 2
        return 0
    except (WitnessRejected,ValueError,sqlite3.Error,OSError) as ex:
        print('WITNESS REJECTED: '+str(ex),file=sys.stderr)
        return 2

if __name__=='__main__':sys.exit(main())
