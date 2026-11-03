"""Frozen CH40-G research-only producer-trace pin and strict receipt policy.
Static source hashes are committed with this code, never taken from client JSON.
"""
import json,re
from pathlib import Path
HEX=re.compile(r'^[0-9a-f]{64}$')
ORIGINAL_ARCHIVE_SHA256='9e713b102982ea09fecbcfbd27bccf55d56808188bfc3e5be1ba76922000ae6b'
PINNED=json.loads('{"one_event_n160_i00":{"certificate_sha256":"7b684e72740d33540ba54bf0024de0854cc518ca4ef52e30c326879384fd770d","original_case_sha256":"d30387f52c5f7f34f585767c3875a90849e83799c18705c847a6202039e1a126","trace_sha256":"24f6d50a3bf5d983ebf8d90f3da8dcad2398c378355bec05a3db5c272ad8d624"},"one_event_n80_i00":{"certificate_sha256":"9939925f8acf1ec0fa31062fd5e3e124af088b2e31a748eabb93eeb270b97d91","original_case_sha256":"8ca568f0e0e8b2167c2e5a416f4758aa303ce4d57815bc5b69ff253c4844ded2","trace_sha256":"a875e26c2d41c22145d137bab4fddc1b444f0bf664ca8456584025bce6cce27b"},"quasi_separated_n160_i00":{"certificate_sha256":"d4c6f76628f32ede2a5689d265816171a76d070d3b11f901c93aca71beed74b1","original_case_sha256":"2172cec5c129a1eaa880a14c17fa82b24dbad7474a5c76af289048a2a3b6cd59","trace_sha256":"bb71de02722e88124b07c744e29a222f507e6769c79b0ccbe435f093050c0f89"},"quasi_separated_n80_i00":{"certificate_sha256":"b6ca9ebbb9187626b5b5547893e7212578157e02239184d4f9110c2c967c9b68","original_case_sha256":"600eed8e4efe6a01f77a6f2c8602d5c9b817a8e1079a69405f024ad7219bbdae","trace_sha256":"2d156dc3a0635da1f00304edf127dde69e79696c66bbc66d77963776fc5e3ef8"},"rare_1pct_n160_i00":{"certificate_sha256":"fe0b3d82dac3c26688251a75f653c808d1dc0ed6f6c580e30169c8203ef4bd64","original_case_sha256":"1e8b0deb8dd829edeadd08ad0220a5d2a521a4ca5139b9d916f747b16924428f","trace_sha256":"64a64dcbe5006b18d09f3d973d0ea8623c1514f4fe9bd83e6d7339b5867c3907"},"rare_1pct_n160_i13":{"certificate_sha256":"ae100aaee94891b589f9252b5c0339f40415d9028f99f92caec4d8a7cbab1a97","original_case_sha256":"90a2149bc0fb52ba1a67c2a3302e92a8eb6d16bf2e594c06964fdf1a0be08af3","trace_sha256":"68dabdd5345184630f8ba05518706579f9d776d0f9c4a4eb25bb6013ebc1413d"},"rare_1pct_n80_i00":{"certificate_sha256":"dddad9ac55a927897a5a0506f1acf561c6d5028e996560bea876b5d6d9af2b30","original_case_sha256":"dfb8a14ec69bab3043137458e85481682a567e751b51b10da815f8907831edb5","trace_sha256":"1ccaad21a2edda191852df587fc0e7496a0827cf705cb6e96081027905cd1c3b"},"rare_5pct_n160_i00":{"certificate_sha256":"15a3f43f49ee51ce6d8347db162072d93b9dec6e43366418ca10be47cb6035b0","original_case_sha256":"fbcbed044f9ef67bfa15e5cf19910369c41abe204f970cee19766cfaf32b264b","trace_sha256":"590b8c6bd5c70cc634457a85f0646f01c1e62f9bd4d583c2fa982397a0d9606c"},"rare_5pct_n80_i00":{"certificate_sha256":"2cfff2cdbb8ae4be359c210243e91a73252894fe985f6c412409c039171e4a3e","original_case_sha256":"9785aedc6fdd221029f37f64179db2e66317a047fdf41fcbed3cb41467b0f1a8","trace_sha256":"20876767b3a53cbfd257650926a18efefad13b259047722c98497a864bb8a09a"},"zero_balanced_n160_i00":{"certificate_sha256":"2d8e60fd63fa1cfd2e3da569e1b9e74b372cedab8a6c59a96290edb550a86a3c","original_case_sha256":"25902f678d3ef27d2a6a70a1b2cfd2587559364b7e6d42b4a5c748608a80f0dc","trace_sha256":"3dd2dfe0be64c0869cec4e174727b3a6ff015cab9196b971ab8a2acbcf92b505"},"zero_balanced_n80_i00":{"certificate_sha256":"cf142e02a904d7367860d24b0c0133caefd2e5f61c06cb9f84463fd6c913eb22","original_case_sha256":"1c0ae4868190a114efaea20576192f55e23eaf4cff1528bec0887bff1815f09e","trace_sha256":"3a699c4816f1e72e31090d4d2fae766fe6084210f940ad994d62e03a315f248a"},"zero_imbalanced_n160_i00":{"certificate_sha256":"7c9fb0d8c2e15a83cc8719c5584d411874f641a8b056dcd227e6e5836af8c95b","original_case_sha256":"16055cfc550f6a1264d9c47c56248237f684f6af2f0de094205739cb581bfcc2","trace_sha256":"a83c408dd3b208b9da35e5043be5a336b2de13c6ff37212d2685d219432e48a3"},"zero_imbalanced_n160_i05":{"certificate_sha256":"72c503ba2efbd07a5242601689be956076ad540c25947fdf1e565ea9b73ba78a","original_case_sha256":"651be709c4fe300c9a92472a1d0e342c53fb93d5e3f68bf3a963a100d75680ef","trace_sha256":"77eefe0d586259395fcb05661eedb83559d6983d0894b1463c10cf82a27d3588"},"zero_imbalanced_n160_i07":{"certificate_sha256":"7ae4ff62d0f99d41366441d35eb7788bbe9c14150623a628cff57379321737ac","original_case_sha256":"bb68bb56a94fdf600a3db1e295e06d1469c24f40beff361ee86a378f29345dc1","trace_sha256":"0a7d58fbec3a6e755bcc20cd2c212beef8066f416e896b1ad013cbd22771a7e6"},"zero_imbalanced_n80_i00":{"certificate_sha256":"873ca3782572e493b614e4189cbcea4c29910187ae2681bb81c8b69153331416","original_case_sha256":"bb4129fdf4aecf0886de61ee3a9d761ebf59d7616d164871b27855a4d41c6e40","trace_sha256":"81f8327c782d5ecd5b8e633e7c59b23457eb4f2a9b4be77b555018cac52df58d"}}')
CAP_COUNT_PINS=json.loads('{"one_event_n160_i00":{"coupled":45,"direct":82},"one_event_n80_i00":{"coupled":44,"direct":83},"quasi_separated_n160_i00":{"coupled":31,"direct":96},"quasi_separated_n80_i00":{"coupled":4,"direct":123},"rare_1pct_n160_i00":{"coupled":39,"direct":88},"rare_1pct_n160_i13":{"coupled":38,"direct":89},"rare_1pct_n80_i00":{"coupled":38,"direct":89},"rare_5pct_n160_i00":{"coupled":14,"direct":113},"rare_5pct_n80_i00":{"coupled":33,"direct":94},"zero_balanced_n160_i00":{"coupled":42,"direct":85},"zero_balanced_n80_i00":{"coupled":43,"direct":84},"zero_imbalanced_n160_i00":{"coupled":36,"direct":91},"zero_imbalanced_n160_i05":{"coupled":43,"direct":84},"zero_imbalanced_n160_i07":{"coupled":19,"direct":108},"zero_imbalanced_n80_i00":{"coupled":47,"direct":80}}')
SCOPE='ORIGINAL_MPFR_DIRECT_COUPLED_AND_INHERITED_LOCAL_CAPS_RESEARCH_ONLY'
REQUIRED={'protocol','case_id','nonce','policy_sha256','original_archive_sha256','original_case_sha256',
          'original_head_sha256','checkpoint_sha256','certificate_sha256','producer_trace_sha256','node_count',
          'direct_caps_certified','coupled_caps_certified','inherited_caps_certified','unsupported_caps','scope',
          'checker_result','scientific_release','global_optimality_certified','attestation_policy'}

def validate_caps(receipt,case,nonce,policy_sha,pin):
    if type(receipt)!=dict or set(receipt)!=REQUIRED:raise ValueError('CH40G missing/fabricated certificate fields')
    if case not in PINNED:raise ValueError('Unfrozen case')
    frozen=PINNED[case]
    want={'protocol':'CH40F-CHECKER-FINITE-ROOT-CAPS-V1','case_id':case,'nonce':nonce,
          'policy_sha256':policy_sha,'original_archive_sha256':ORIGINAL_ARCHIVE_SHA256,
          'original_case_sha256':frozen['original_case_sha256'],
          'original_head_sha256':pin['original_head_sha256'],
          'checkpoint_sha256':pin['checkpoint_sha256'],
          'certificate_sha256':frozen['certificate_sha256'],
          'producer_trace_sha256':frozen['trace_sha256'],
          'node_count':127,'inherited_caps_certified':127,'unsupported_caps':0,
          'scope':SCOPE,'checker_result':'INDEPENDENT_MATH_CERTIFIED_FINITE_CAPS',
          'scientific_release':'NO_GO','global_optimality_certified':False,
          'attestation_policy':'RESEARCH_ONLY_NEVER_PRODUCTION_OR_SCIENTIFIC_GO'}
    for key,value in want.items():
        if type(receipt[key])!=type(value) or receipt[key]!=value:raise ValueError('CH40G untrusted claim: '+key)
    d,c=receipt['direct_caps_certified'],receipt['coupled_caps_certified']
    if type(d)!=int or type(c)!=int or d<0 or c<0 or d+c!=127:raise ValueError('Incomplete cap arithmetic')
    if d!=CAP_COUNT_PINS[case]['direct'] or c!=CAP_COUNT_PINS[case]['coupled']:
        raise ValueError('Wrong frozen direct/coupled cap distribution')
    if type(nonce)!=str or not HEX.fullmatch(nonce):raise ValueError('Invalid challenge nonce')
    return receipt
