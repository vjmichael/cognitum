from dataclasses import dataclass
from threading import RLock
from .contracts import Manifest

@dataclass(frozen=True)
class Entry:
    factory: type
    manifest: Manifest
    enabled: bool

class Registry:
    """Trusted installation only. Disable affects new admissions, not running calls."""
    def __init__(self):
        self.lock = RLock()
        self._entries = {}
        self._champions = {}

    def install(self, factory, *, enabled=False):
        # Lifecycle hooks are trusted code, not a third-party loading boundary.
        plugin = factory()
        manifest = plugin.manifest()
        if not isinstance(manifest, Manifest) or plugin.health() is not True or plugin.self_test() is not True:
            raise ValueError("plugin validation failed")
        with self.lock:
            self._entries[manifest.name] = Entry(factory, manifest, enabled)
        return manifest

    def enable(self, name, enabled=True):
        if type(enabled) is not bool:
            raise ValueError("enable requires boolean")
        with self.lock:
            e = self._entries[name]
            self._entries[name] = Entry(e.factory, e.manifest, enabled)

    def nominate(self, slot, name):
        with self.lock:
            if not any(o.slot == slot for o in self._entries[name].manifest.operations):
                raise ValueError("slot not provided")
            self._champions[slot] = name

    def resolve(self, operation, allow_research=False):
        with self.lock:
            for name in sorted(self._entries):
                e = self._entries[name]
                if not e.enabled or (e.manifest.track == "research" and not allow_research):
                    continue
                for op in e.manifest.operations:
                    if op.name == operation and self._champions.get(op.slot) == name:
                        return e, op
        return None

    def snapshot(self):
        with self.lock:
            return {"plugins": [{**e.manifest.describe(), "enabled": e.enabled}
                                for _, e in sorted(self._entries.items())],
                    "champions": dict(sorted(self._champions.items()))}
