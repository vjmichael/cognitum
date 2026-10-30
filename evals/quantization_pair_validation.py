"""Preflight *external-export* JSON manifest for matched Lu/Cognitum trials.

This is offline experiment configuration linting, NOT Lu's Protobuf command
interface, not an inference benchmark, and not measurement verification.
No network, executable launch, model execution, or file system mutation.
"""
from __future__ import annotations
import json
import re

SHA = re.compile(r'[0-9a-f]{64}\Z')
TIERS = {'sub-1b','1b','7b-14b','16b','25b-35b'}
KV = {'f16','q8_0','q4_0'}

class ManifestError(ValueError):
    pass


def _require_sha(value, label):
    if not isinstance(value,str) or SHA.fullmatch(value) is None:
        raise ManifestError('INVALID_SHA256_'+label.upper())


def _str(value, label):
    if not isinstance(value,str) or not value.strip():
        raise ManifestError('MISSING_'+label.upper())


def validate_protocol(protocol):
    if not isinstance(protocol,dict) or protocol.get('protocol_version')!=2:
        raise ManifestError('INVALID_PROTOCOL_VERSION')
    cells=protocol.get('cells')
    if not isinstance(cells,list) or not cells:
        raise ManifestError('NO_EXPERIMENT_CELLS')
    identity_seen={}
    pair_ids=set()
    for i,c in enumerate(cells):
        if not isinstance(c,dict) or c.get('tier') not in TIERS:
            raise ManifestError('INVALID_MODEL_SIZE_TIER')
        model=c.get('model')
        settings=c.get('settings')
        if not isinstance(model,dict) or not isinstance(settings,dict):
            raise ManifestError('INVALID_MODEL_OR_SETTINGS')
        for key in ('model_id','architecture','tokenizer_revision','chat_template_revision',
                    'quantizer_id','weight_quantization','weight_bits_per_weight'):
            _str(model.get(key),key)
        for key in ('source_checkpoint_sha256','quantized_artifact_sha256',
                    'quantizer_build_sha256'):
            _require_sha(model.get(key),key)
        model_id=model['model_id']; source=model['source_checkpoint_sha256']
        if model_id in identity_seen and identity_seen[model_id] != source:
            raise ManifestError('MODEL_ID_REUSED_WITH_DIFFERENT_SOURCE')
        identity_seen[model_id]=source
        for key in ('engine_build_id','backend_kind','hardware_id',
                    'sampler_id','task_suite_sha256','scorer_sha256',
                    'base_prompt_sha256','tokenizer_sha256'):
            if key.endswith('_sha256'):_require_sha(settings.get(key),key)
            else:_str(settings.get(key),key)
        for key in ('requested_k_type','requested_v_type','effective_k_type','effective_v_type'):
            if settings.get(key) not in KV:
                raise ManifestError('UNSUPPORTED_OR_UNCONFIRMED_KV_TYPE')
        if (settings['requested_k_type']!=settings['effective_k_type'] or
            settings['requested_v_type']!=settings['effective_v_type']):
            raise ManifestError('CACHE_QUANTIZATION_NOT_EFFECTIVE')
        if settings['requested_v_type']!='f16' and settings.get('flash_attention') is not True:
            raise ManifestError('QUANTIZED_VALUE_CACHE_REQUIRES_FLASH_ATTENTION')
        if (settings['requested_k_type']!=settings['requested_v_type'] and
            settings.get('mixed_kv_backend_verified') is not True):
            raise ManifestError('MIXED_CACHE_SUPPORT_NOT_VERIFIED')
        if type(settings.get('context_tokens')) is not int or settings['context_tokens']<128:
            raise ManifestError('INVALID_CONTEXT_LENGTH')
        if type(settings.get('gpu_layers')) is not int or settings['gpu_layers']<0:
            raise ManifestError('INVALID_GPU_OFFLOAD_CONFIGURATION')
        trials=c.get('paired_trials')
        if not isinstance(trials,list) or not trials:
            raise ManifestError('NO_PAIRED_TRIALS')
        for trial in trials:
            if not isinstance(trial,dict):raise ManifestError('INVALID_TRIAL')
            for key in ('task_id','trial_id'):_str(trial.get(key),key)
            if type(trial.get('seed')) is not int or trial['seed']<0:
                raise ManifestError('INVALID_TRIAL_SEED')
            pair_id=(model_id,source,model['quantized_artifact_sha256'],
                settings['requested_k_type'],settings['requested_v_type'],
                trial['task_id'],trial['trial_id'],trial['seed'])
            if pair_id in pair_ids:raise ManifestError('DUPLICATE_TRIAL_PAIR')
            pair_ids.add(pair_id)
            arms=trial.get('arms')
            if not isinstance(arms,list) or len(arms)!=2 or {a.get('cognitum_enabled') for a in arms if isinstance(a,dict)}!={True,False}:
                raise ManifestError('MISSING_MATCHED_ON_OFF_ARMS')
            expected=None
            for a in arms:
                _str(a.get('trace_id'),'trace_id')
                # A same-weights same-settings pair; tool exposure varies by
                # design but *base* prompt + sampler/context/hardware do not.
                for key in ('model_artifact_sha256','engine_build_id','hardware_id',
                            'task_suite_sha256','scorer_sha256','base_prompt_sha256'):
                    _require_sha(a.get(key),key) if key.endswith('sha256') else _str(a.get(key),key)
                fixed={k:a[k] for k in ('model_artifact_sha256','engine_build_id','hardware_id',
                                       'task_suite_sha256','scorer_sha256','base_prompt_sha256')}
                if fixed['model_artifact_sha256']!=model['quantized_artifact_sha256']:
                    raise ManifestError('MODEL_WEIGHTS_MISMATCH')
                for k in ('engine_build_id','hardware_id','task_suite_sha256',
                          'scorer_sha256','base_prompt_sha256'):
                    if fixed[k]!=settings[k]:raise ManifestError('ARM_SETTINGS_NOT_MATCHED')
                if expected is None:expected=fixed
                elif fixed!=expected:raise ManifestError('ON_OFF_ARMS_NOT_PAIRED')
    return {'valid': True, 'cells':len(cells), 'pairs':len(pair_ids),
            'model_source_checkpoints':len(set(identity_seen.values())),
            'note':'PROTOCOL_ONLY_NO_MODELS_RUN_OR_RESULTS_VERIFIED'}


def validate_json_bytes(raw):
    if not isinstance(raw,bytes) or len(raw)>2_000_000:
        raise ManifestError('INVALID_MANIFEST_SIZE')
    try: doc=json.loads(raw)
    except Exception as exc:raise ManifestError('INVALID_MANIFEST_JSON') from exc
    return validate_protocol(doc)
