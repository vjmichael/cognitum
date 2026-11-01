"""Explicitly opt-in, research-only adapter to *unchanged* Cognitum Runtime/Registry.

This does NOT self-register, enter production routing, claim hidden-confounding
identification, or grant the Lu host native-tool privileges.
"""
from __future__ import annotations
import json
import os
from cognitum.contracts import Manifest, Operation, Shape
from .c14_research_host import canonical, handle, ACTION

PLUGIN_NAME = 'c14_g25_conditional_research'
SLOT = 'c14_g25_conditional_research'


class G25ConditionalResearchPlugin:
    def manifest(self):
        return Manifest(
          PLUGIN_NAME, '0.1.0',
          (Operation(ACTION,SLOT,
             Shape((('request_json',131072),)),Shape((('report_json',8192),)),
             assurance='unverified',outcome_kind='conditional_sensitivity_research_report'),),
          track='research',maturity='prototype')

    def health(self):
        return os.environ.get('COGNITUM_G25_RESEARCH_OPT_IN')=='1'

    def self_test(self):
        if not self.health():return False
        sample={'schema_version':1,'request_id':'plugin-selftest', 'action':ACTION,
          'counts':[[[50,50],[50,50]],[[50,50],[50,50]]],'gamma':.25,
          'assumption_evidence':{
             'sampling_iid_supported':True,'consistency_supported':True,
             'measurement_validity_supported':True,
             'gamma_justification':'Research-only predetermined sensitivity scenario'}}
        answer=handle(canonical(sample).encode(),set())
        return (answer['host_status']=='completed'
             and answer['automatic_causal_certification'] is False
             and answer['production_estimator_promotion'] is False)

    def handle(self,operation,payload):
        if not self.health() or operation!=ACTION:
            raise ValueError('research-only capability disabled or wrong action')
        if type(payload) is not dict or set(payload)!={'request_json'} or type(payload['request_json']) is not str:
            raise ValueError('invalid research-plugin request shape')
        raw=payload['request_json'].encode('utf-8')
        if not 0<len(raw)<=131072:
            raise ValueError('request size exceeds bounded native plugin contract')
        answer=handle(raw,set())
        # Outer Cognitum runtime tracks *worker execution*. This inner status
        # tracks refusal or conditional report; do NOT conflate 'completed' with
        # scientific admission.
        return {'report_json':canonical(answer)}
