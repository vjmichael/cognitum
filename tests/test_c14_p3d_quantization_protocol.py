"""Validate that a benchmark cell really compares identical quantized model weights."""
import copy
import json
import unittest
from evals.quantization_pair_validation import validate_protocol, validate_json_bytes, ManifestError

H='a'*64
B='b'*64
C='c'*64
D='d'*64
E='e'*64

def fixture():
    arm={'trace_id':'sample-trace','model_artifact_sha256':B,
         'engine_build_id':'llamacpp-pinned-build','hardware_id':'gpu0',
         'task_suite_sha256':C,'scorer_sha256':D,'base_prompt_sha256':E}
    off=dict(arm,cognitum_enabled=False)
    on=dict(arm,cognitum_enabled=True,trace_id='sample-trace-2')
    return {'protocol_version':2,'cells':[{'tier':'7b-14b',
        'model':{'model_id':'family-8b-revision','architecture':'dense',
            'tokenizer_revision':'frozen-rev','chat_template_revision':'frozen-rev',
            'source_checkpoint_sha256':H,'quantized_artifact_sha256':B,
            'quantizer_id':'llama-quantize-commit','quantizer_build_sha256':C,
            'weight_quantization':'Q4_K_M','weight_bits_per_weight':'4.8'},
        'settings':{'engine_build_id':'llamacpp-pinned-build','backend_kind':'llama.cpp',
            'hardware_id':'gpu0','sampler_id':'temp-0','task_suite_sha256':C,
            'scorer_sha256':D,'base_prompt_sha256':E,'tokenizer_sha256':H,
            'requested_k_type':'q8_0','requested_v_type':'q8_0',
            'effective_k_type':'q8_0','effective_v_type':'q8_0',
            'flash_attention':True,'mixed_kv_backend_verified':False,
            'context_tokens':4096,'gpu_layers':22},
        'paired_trials':[{'task_id':'t1','trial_id':'rep1','seed':42,
            'arms':[on,off]}]}]}

class TestQuantizationPairedProtocol(unittest.TestCase):
    def test_valid_two_arm_block(self):
        r=validate_protocol(fixture())
        self.assertEqual((r['cells'],r['pairs']),(1,1))
        self.assertIn('NO_MODELS_RUN',r['note'])
    def test_bytes_valid(self):
        self.assertTrue(validate_json_bytes(json.dumps(fixture()).encode())['valid'])
    def test_changed_model_weights(self):
        doc=fixture();doc['cells'][0]['paired_trials'][0]['arms'][0]['model_artifact_sha256']=H
        with self.assertRaisesRegex(ManifestError,'MODEL_WEIGHTS_MISMATCH'):validate_protocol(doc)
    def test_different_model_families_cannot_share_pair(self):
        doc=fixture();doc['cells'][0]['paired_trials'][0]['arms'][1]['model_artifact_sha256']=C
        with self.assertRaises(ManifestError):validate_protocol(doc)
    def test_reused_model_id_different_source(self):
        doc=fixture();second=copy.deepcopy(doc['cells'][0]);second['model']['source_checkpoint_sha256']=C
        second['paired_trials'][0]['trial_id']='rep2'
        doc['cells'].append(second)
        with self.assertRaisesRegex(ManifestError,'MODEL_ID_REUSED_WITH_DIFFERENT_SOURCE'):validate_protocol(doc)
    def test_cache_quantization_must_match_actual_runtime(self):
        doc=fixture();doc['cells'][0]['settings']['effective_v_type']='q4_0'
        with self.assertRaisesRegex(ManifestError,'CACHE_QUANTIZATION_NOT_EFFECTIVE'):validate_protocol(doc)
    def test_flash_attention_needed_for_v(self):
        doc=fixture();doc['cells'][0]['settings']['flash_attention']=False
        with self.assertRaisesRegex(ManifestError,'QUANTIZED_VALUE_CACHE_REQUIRES_FLASH_ATTENTION'):validate_protocol(doc)
    def test_mixed_kv_needs_verified_backend(self):
        doc=fixture();doc['cells'][0]['settings'].update(requested_v_type='q4_0',effective_v_type='q4_0')
        with self.assertRaisesRegex(ManifestError,'MIXED_CACHE_SUPPORT_NOT_VERIFIED'):validate_protocol(doc)
        doc['cells'][0]['settings']['mixed_kv_backend_verified']=True
        self.assertTrue(validate_protocol(doc)['valid'])
    def test_no_model_substitution_in_missing_arm(self):
        doc=fixture();doc['cells'][0]['paired_trials'][0]['arms'].pop()
        with self.assertRaisesRegex(ManifestError,'MISSING_MATCHED_ON_OFF_ARMS'):validate_protocol(doc)
    def test_runtime_must_match(self):
        doc=fixture();doc['cells'][0]['paired_trials'][0]['arms'][1]['engine_build_id']='other'
        with self.assertRaisesRegex(ManifestError,'ARM_SETTINGS_NOT_MATCHED'):validate_protocol(doc)
    def test_invalid_source_hash_rejected(self):
        doc=fixture();doc['cells'][0]['model']['source_checkpoint_sha256']='junk'
        with self.assertRaises(ManifestError):validate_protocol(doc)
    def test_no_duplicate_trials(self):
        doc=fixture();doc['cells'][0]['paired_trials'].append(copy.deepcopy(doc['cells'][0]['paired_trials'][0]))
        with self.assertRaisesRegex(ManifestError,'DUPLICATE_TRIAL_PAIR'):validate_protocol(doc)
    def test_no_invalid_manifest(self):
        for raw in (b'foo',b' '*2_000_001):
            with self.assertRaises(ManifestError):validate_json_bytes(raw)

if __name__=='__main__':unittest.main()
