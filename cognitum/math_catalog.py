"""Inert native Protobuf discovery metadata for six C05 specialists.

These developer-authored use/avoid rules are advisory to a FUTURE Lu-owned
catalog. Never install, enable, grant or advertise a tool from these bytes.
Lu owns approval, authentic publisher enrollment, resource isolation and
whether the currently loaded model can safely use each operation.
"""
from google.protobuf.message import DecodeError
from .proto import specialists_pb2 as pb

CATALOG_TYPE_URL="type.googleapis.com/cognitum.math.v1.SpecialistCatalog"
ENTRIES=(
    ("symbolic","exact_symbolic",
     "Expand or differentiate a one-variable rational polynomial in x of degree at most six.",
     "Avoid general symbolic integration, arbitrary equations, variable units or user-provided Python code."),
    ("scientific","numerical_approximation",
     "Approximate sin/cos in radians, exp, log or real sqrt with declared significant digits.",
     "Avoid complex domains, values outside the allowed input range or claims of certified error bounds."),
    ("precision","finite_precision_decimal",
     "Evaluate decimal add/divide/sqrt with explicitly chosen 15–80 digit decimal precision.",
     "Avoid representing rounded decimal results as exact fractions or proofs of user intent."),
    ("linear","exact_rational_linear",
     "Compute exact determinant, multiply or solve small rational matrices up to 4 by 4.",
     "Avoid ill-conditioned numerical floating-point benchmarking, huge matrices or unit-free inference."),
    ("root","exact_bracketed_polynomial_interval",
     "Bound a real root of a degree-six-or-lower polynomial with an explicit sign-changing bracket.",
     "Avoid unbracketed roots, general nonlinear systems and unverified root uniqueness claims."),
    ("simulation","discrete_model_not_certified",
     "Run a bounded symplectic-Euler reference simulation for a scalar harmonic oscillator.",
     "Avoid treating a discrete trajectory as an exact continuous ODE or validated physical prediction."),
)

def catalog():
    message=pb.SpecialistCatalog(schema_version=1,host_approved=False)
    for kind, assurance, use, avoid in ENTRIES:
        cls=kind.title()+"Request"
        output=kind.title()+"Result"
        # Standalone backend uses explicit domain-native Protobuf types, not JSON.
        message.specialists.add(
            operation="cognitum.math."+kind,
            input_type_url="type.googleapis.com/cognitum.math.v1."+cls,
            output_type_url="type.googleapis.com/cognitum.math.v1."+output,
            use_when=use,avoid_when=avoid,assurance=assurance,
            registered=False,model_advertised=False)
    return message

def encode_catalog():
    return catalog().SerializeToString(deterministic=True)

def decode_catalog(data):
    if type(data) is not bytes or not 0<len(data)<=8192:
        raise ValueError("invalid bounded specialist catalog frame")
    message=pb.SpecialistCatalog()
    try:
        message.ParseFromString(data)
    except DecodeError as err:
        raise ValueError("malformed specialist catalog") from err
    trimmed=pb.SpecialistCatalog()
    trimmed.CopyFrom(message)
    trimmed.DiscardUnknownFields()
    if trimmed!=message or message.SerializeToString(deterministic=True)!=data:
        raise ValueError("unknown or noncanonical catalog fields")
    if message!=catalog():
        raise ValueError("unapproved specialist metadata or activation claim")
    return message
