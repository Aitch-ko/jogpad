import asyncio
import threading

from jogpad.events import EventHub


def test_event_from_another_thread_reaches_subscriber() -> None:
    async def scenario() -> tuple[int, int]:
        hub = EventHub()
        queue = hub.subscribe()
        threading.Thread(target=hub.publish, args=((77, 1),)).start()
        return await asyncio.wait_for(queue.get(), 1)

    assert asyncio.run(scenario()) == (77, 1)


def test_unsubscribed_queue_gets_nothing() -> None:
    async def scenario() -> bool:
        hub = EventHub()
        queue = hub.subscribe()
        hub.unsubscribe(queue)
        hub.publish((77, 1))
        await asyncio.sleep(0.01)
        return queue.empty()

    assert asyncio.run(scenario())


def test_full_queue_drops_instead_of_blocking() -> None:
    async def scenario() -> int:
        hub = EventHub()
        queue = hub.subscribe()
        for _ in range(500):
            hub.publish((77, 1))
        await asyncio.sleep(0.05)
        return queue.qsize()

    assert asyncio.run(scenario()) == 100
