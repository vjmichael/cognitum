"""C15 typed 3D scene geometry with established NumPy/SciPy primitives.

All observations are caller supplied; no cameras, images, GPU, filesystem,
Lu tools or unapproved observations accessed. Frame transforms are rigid;
metric coordinates are not latent embeddings.
"""
from dataclasses import dataclass
from math import isfinite

MAX_OBJECTS=64
MAX_FRAMES=16
MAX_COORD=1_000_000


@dataclass(frozen=True)
class Frame:
    name: str
    parent: str
    translation_m: tuple[float,float,float]
    quaternion_xyzw: tuple[float,float,float,float]


@dataclass(frozen=True)
class SceneObject:
    stable_id: str
    frame: str
    position_m: tuple[float,float,float]
    dimensions_m: tuple[float,float,float]
    visible: bool
    observation_source: str
    timestamp_ms: int
    version: int = 1
    orientation_xyzw: tuple[float,float,float,float] = (0.,0.,0.,1.)
    geometry_ref: str = "unresolved"
    confidence: float = 0.0


@dataclass(frozen=True)
class Scene:
    frames: tuple[Frame,...]
    objects: tuple[SceneObject,...]
    epoch: int


def _ident(value):
    return (type(value) is str and value.isascii() and value.isidentifier()
            and 1<=len(value)<=48)


def _numbers(values, length, *, positive=False):
    return (type(values) is tuple and len(values)==length
            and all(type(v) in (int,float) and isfinite(v)
                    and abs(v)<=MAX_COORD and (v>0 if positive else True)
                    for v in values))


def validate(scene:Scene):
    if (type(scene) is not Scene or type(scene.frames) is not tuple
            or type(scene.objects) is not tuple or not 0<=len(scene.frames)<=MAX_FRAMES
            or len(scene.objects)>MAX_OBJECTS or type(scene.epoch) is not int
            or not 0<=scene.epoch<=2**53):
        raise ValueError("invalid bounded scene")
    names={"world"}
    frame_map={}
    for frame in scene.frames:
        if (type(frame) is not Frame or not _ident(frame.name)
                or frame.name in names or not _ident(frame.parent)
                or not _numbers(frame.translation_m,3)
                or not _numbers(frame.quaternion_xyzw,4)
                or not 0.999999<=sum(q*q for q in frame.quaternion_xyzw)<=1.000001):
            raise ValueError("invalid rigid coordinate frame")
        names.add(frame.name)
        frame_map[frame.name]=frame
    for name in frame_map:
        visited={name}
        current=name
        while current!="world":
            if current not in frame_map:
                raise ValueError("missing parent frame")
            current=frame_map[current].parent
            if current in visited:
                raise ValueError("cycle in coordinate frames")
            visited.add(current)
    ids=set()
    for obj in scene.objects:
        if (type(obj) is not SceneObject or not _ident(obj.stable_id)
                or obj.stable_id in ids or obj.frame not in names
                or not _numbers(obj.position_m,3)
                or not _numbers(obj.dimensions_m,3,positive=True)
                or not _ident(obj.observation_source)
                or not _numbers(obj.orientation_xyzw,4)
                or not 0.999999<=sum(q*q for q in obj.orientation_xyzw)<=1.000001
                or type(obj.geometry_ref) is not str
                or not 1<=len(obj.geometry_ref)<=256
                or not all(c.isascii() and (c.isalnum() or c in "._:/-")
                           for c in obj.geometry_ref)
                or type(obj.confidence) not in (float,int)
                or not isfinite(obj.confidence) or not 0<=obj.confidence<=1
                or type(obj.visible) is not bool
                or type(obj.timestamp_ms) is not int or obj.timestamp_ms<0
                or obj.timestamp_ms>scene.epoch or type(obj.version) is not int
                or obj.version<1):
            raise ValueError("invalid scene object identity/evidence")
        ids.add(obj.stable_id)
    return scene


def world_position(scene:Scene, stable_id:str)->tuple[float,float,float]:
    """Transform local metric position into world via SciPy quaternion rotation."""
    validate(scene)
    obj=next((o for o in scene.objects if o.stable_id==stable_id),None)
    if obj is None:
        raise ValueError("unknown object stable ID")
    try:
        import numpy as np
        from scipy.spatial.transform import Rotation
    except ImportError as exc:
        raise RuntimeError("scipy/numpy_geometry_backend_unavailable") from exc
    current=obj.frame
    position=np.array(obj.position_m,dtype=np.float64)
    frames={f.name:f for f in scene.frames}
    while current!="world":
        frame=frames[current]
        position=Rotation.from_quat(frame.quaternion_xyzw).apply(position)
        position+=np.array(frame.translation_m,dtype=np.float64)
        current=frame.parent
    if not np.all(np.isfinite(position)):
        raise ValueError("nonfinite transformed position")
    return tuple(float(x) for x in position)


def relation(scene:Scene, first:str, second:str, *, tolerance_m:float=1e-6)->dict:
    """Deterministic metric world-frame relation, not learned perception."""
    if type(tolerance_m) not in (int,float) or not isfinite(tolerance_m) or not 0<=tolerance_m<=1:
        raise ValueError("invalid relation tolerance")
    a=world_position(scene,first)
    b=world_position(scene,second)
    from math import dist
    separation=dist(a,b)
    return {"distance_m":separation,
            "coincident":separation<=tolerance_m,
            "first_left_of_second":a[0]<b[0]-tolerance_m,
            "first_below_second":a[2]<b[2]-tolerance_m,
            "frame":"world",
            "evidence_kind":"caller_supplied_metric_geometry"}


def world_pose(scene:Scene,stable_id:str):
    """Full world SE(3) pose: translated position and composed orientation."""
    validate(scene)
    try:
        import numpy as np
        from scipy.spatial.transform import Rotation
    except ImportError as exc:
        raise RuntimeError("scipy/numpy_geometry_backend_unavailable") from exc
    obj=next((o for o in scene.objects if o.stable_id==stable_id),None)
    if obj is None:raise ValueError("unknown object stable ID")
    position=np.asarray(obj.position_m,dtype=np.float64)
    rotation=Rotation.from_quat(obj.orientation_xyzw)
    frames={f.name:f for f in scene.frames}
    current=obj.frame
    while current!="world":
        frame=frames[current]
        q=Rotation.from_quat(frame.quaternion_xyzw)
        position=q.apply(position)+np.asarray(frame.translation_m,dtype=np.float64)
        rotation=q*rotation
        current=frame.parent
    return tuple(float(x) for x in position),tuple(float(x) for x in rotation.as_quat())
