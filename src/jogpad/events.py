"""Hands key events from the reader threads to the web page's live view.

Readers run in plain threads, the web server in asyncio. Each subscriber gets
its own bounded queue; a page that stops reading loses events, it never blocks
the readers.
"""

from __future__ import annotations

import asyncio
import contextlib
import threading

QUEUE_SIZE = 100

# (key code, value) as read from the device
Event = tuple[int, int]


class EventHub:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._subscribers: list[tuple[asyncio.AbstractEventLoop, asyncio.Queue[Event]]] = []

    def publish(self, event: Event) -> None:
        with self._lock:
            subscribers = list(self._subscribers)
        for loop, queue in subscribers:
            with contextlib.suppress(RuntimeError):  # loop already closed
                loop.call_soon_threadsafe(_put, queue, event)

    def subscribe(self) -> asyncio.Queue[Event]:
        queue: asyncio.Queue[Event] = asyncio.Queue(QUEUE_SIZE)
        with self._lock:
            self._subscribers.append((asyncio.get_running_loop(), queue))
        return queue

    def unsubscribe(self, queue: asyncio.Queue[Event]) -> None:
        with self._lock:
            self._subscribers = [s for s in self._subscribers if s[1] is not queue]


def _put(queue: asyncio.Queue[Event], event: Event) -> None:
    with contextlib.suppress(asyncio.QueueFull):
        queue.put_nowait(event)
