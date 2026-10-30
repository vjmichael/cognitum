"""Validate format of externally extracted 128-D appearance evidence.

Hashes of source bytes are not signatures; content hashes alone do not establish
that a person, camera or sensor generated an authentic feature. This module
never permits identity promotion or external action.
"""
from __future__ import annotations
from cognitum.proto import spatial_appearance_pb2 as pb
import math

class AppearanceRejected(ValueError):pass

def assess(spec:pb.AppearanceDescriptor)->pb.AppearanceAssessment:
    if not isinstance(spec,pb.AppearanceDescriptor) or spec.schema_version!=1 or not spec.research_only or spec.grants_authority:raise AppearanceRejected('INVALID_RESEARCH_CONTRACT')
    for value in (spec.model_id,spec.image_source_id,spec.detection_id,spec.conversation_id):
        if not value or len(value)>128 or not all(c.isascii() and (c.isalnum() or c in '-_:.') for c in value):raise AppearanceRejected('INVALID_IDENTIFIER')
    if spec.frame<=0:raise AppearanceRejected('INVALID_FRAME')
    if len(spec.encoder_sha256)!=32 or len(spec.frame_sha256)!=32:raise AppearanceRejected('MISSING_CONTENT_DIGEST')
    if len(spec.vector)!=128 or any(not math.isfinite(x) or abs(x)>100 for x in spec.vector):raise AppearanceRejected('INVALID_128D_VECTOR')
    norm=math.sqrt(sum(x*x for x in spec.vector))
    if not .99<=norm<=1.01:raise AppearanceRejected('FEATURE_NOT_UNIT_NORMALIZED')
    return pb.AppearanceAssessment(format_valid=True,content_hashes_well_formed=True,independently_authenticated=False,research_only=True,grants_authority=False,warnings=['CONTENT_DIGEST_IS_NOT_A_SOURCE_SIGNATURE','ENCODER_NOT_ATTESTED','NO_INDEPENDENT_IMAGE_OR_PERSON_IDENTITY_VERIFICATION','NO_ACTION_AUTHORITY'])
