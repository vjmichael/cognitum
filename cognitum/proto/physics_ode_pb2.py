"""Descriptor-backed C16 ODE Protobuf classes; exact source checked by protoc."""
from google.protobuf import descriptor_pb2 as d,descriptor_pool,message_factory
f=d.FileDescriptorProto()
f.name="cognitum/physics/v1/ode.proto";f.package="cognitum.physics_ode.v1";f.syntax="proto3"
T=d.FieldDescriptorProto
def fld(name,kind,rep=False,ref=None):return name,kind,rep,ref
def msg(name,fields):
    m=f.message_type.add();m.name=name
    for i,(key,kind,rep,ref) in enumerate(fields,1):
        field=m.field.add();field.name=key;field.number=i
        field.type=getattr(T,"TYPE_"+kind.upper())
        field.label=T.LABEL_REPEATED if rep else T.LABEL_OPTIONAL
        if ref:field.type_name="."+f.package+"."+ref
msg("PhysicalRequest",[
    fld("schema_version","uint32"),fld("kind","string"),fld("unit_system","string"),
    fld("mass_kg","double"),fld("spring_n_per_m","double"),
    fld("damping_n_s_per_m","double"),fld("force_n","double"),
    fld("gravity_m_per_s2","double"),fld("initial_position_m","double"),
    fld("initial_velocity_m_per_s","double"),fld("t_end_s","double"),
    fld("output_steps","uint32"),fld("rtol","double"),fld("atol","double"),
    fld("method","string"),fld("max_internal_step_s","double"),
    fld("max_function_evals","uint32"),fld("has_stop_boundary","bool"),
    fld("stop_at_position_m","double"),fld("validation_domain","string")])
msg("PhysicsSample",[
    fld("t_s","double"),fld("position_m","double"),
    fld("velocity_m_per_s","double"),fld("mechanical_energy_j","double")])
msg("PhysicalResult",[
    fld("schema_version","uint32"),fld("status","string"),
    fld("samples","message",True,"PhysicsSample"),
    fld("solver_method","string"),fld("requested_rtol","double"),
    fld("requested_atol","double"),fld("function_evals","uint32"),
    fld("has_analytic_comparison","bool"),fld("convergence_max_error_m","double"),
    fld("has_balance","bool"),fld("max_balance_residual_j","double"),
    fld("max_invariant_relative_drift","double"),fld("has_event","bool"),
    fld("event_time_s","double"),fld("reached_end","bool"),
    fld("request_sha256","string"),fld("limitations","string",True)])
pool=descriptor_pool.DescriptorPool()
DESCRIPTOR=pool.Add(f)
for name in ("PhysicalRequest","PhysicsSample","PhysicalResult"):
    globals()[name]=message_factory.GetMessageClass(pool.FindMessageTypeByName(f.package+"."+name))
