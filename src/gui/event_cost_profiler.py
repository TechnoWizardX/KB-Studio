"""Qt event cost profiler (``KB_CAPTURE_EVENTS=1``).

A QApplication subclass measuring the wall time of every notify() dispatch.
Events that take at least ``KB_EVENT_COST_MS`` (default 100 ms) milliseconds
are printed to stderr with the event type and the receiving class, so a
stall that has no Python frames (pure Qt/C++ work) can still be attributed
to a concrete widget and event. Normal runs (variable unset) are unaffected.
"""

import os
import sys
from time import perf_counter

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QTimer


class EventCostProfilerApp(QApplication):
    _THRESHOLD_MS = float(os.environ.get("KB_EVENT_COST_MS", "100"))

    def notify(self, receiver, event):
        start = perf_counter()
        result = super().notify(receiver, event)
        elapsed = (perf_counter() - start) * 1000
        if elapsed >= self._THRESHOLD_MS:
            event_type = str(event.type()).split(".")[-1]
            print(
                f"[event-cost] {elapsed:.0f}ms {event_type} "
                f"-> {type(receiver).__name__} {_describe_receiver(receiver)}",
                file=sys.stderr,
                flush=True,
            )
        return result


def _describe_receiver(receiver) -> str:
    """Interval/object identity for QTimers (slow timer events are otherwise
    anonymous), plus the parent chain for correlation."""
    parts = []
    if isinstance(receiver, QTimer):
        parts.append(f"interval={receiver.interval()}ms "
                     f"remaining={receiver.remainingTime()}ms")
    name = receiver.objectName()
    if name:
        parts.append(f"objectName={name!r}")
    parent = receiver.parent()
    chain = []
    while parent is not None:
        pname = type(parent).__name__
        pname_name = parent.objectName()
        chain.append(pname + (f"({pname_name})" if pname_name else ""))
        parent = parent.parent()
    if chain:
        chain_text = " < ".join(chain[:5])
        parts.append(f"chain={chain_text}")
    return "{" + ", ".join(parts) + "}" if parts else ""


def app_class_for_environment() -> type:
    """The QApplication class the app was created from (profiled or plain)."""
    if os.environ.get("KB_CAPTURE_EVENTS") == "1":
        return EventCostProfilerApp
    return QApplication
