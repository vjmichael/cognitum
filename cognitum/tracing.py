"""Metadata-only trace by default; payload retention is deliberately absent."""
import json
from threading import Lock

class Trace:
    def __init__(self, path=None):
        self.path = path
        self.events = []
        self.lock = Lock()

    def append(self, event):
        with self.lock:
            if self.path:
                with open(self.path, "a", encoding="utf-8") as stream:
                    stream.write(json.dumps(event, sort_keys=True) + "\n")
            self.events.append(event)
