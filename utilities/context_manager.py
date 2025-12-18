import asyncio
import threading
from typing import Any, Coroutine


class AsyncLoopManager:
    """Manages a persistent event loop in a background thread."""

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self._loop: asyncio.AbstractEventLoop = None
        self._thread: threading.Thread = None
        self._started = threading.Event()
        self._start_loop()
        self._initialized = True

    def _start_loop(self):
        """Start the event loop in a background thread."""

        def run_loop():
            self._loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._loop)
            self._started.set()
            self._loop.run_forever()

        self._thread = threading.Thread(target=run_loop, daemon=True)
        self._thread.start()
        self._started.wait()  # Wait until loop is ready

    def run(self, coro: Coroutine) -> Any:
        """Run a coroutine in the persistent event loop and wait for result."""
        if self._loop is None or self._loop.is_closed():
            self._start_loop()

        future = asyncio.run_coroutine_threadsafe(coro, self._loop)
        return future.result()

    def run_async_generator(self, async_gen):
        """
        Yield items from an async generator in a sync context.
        """

        async def get_next(agen):
            try:
                return await agen.__anext__(), False
            except StopAsyncIteration:
                return None, True

        while True:
            result, done = self.run(get_next(async_gen))
            if done:
                break
            yield result
