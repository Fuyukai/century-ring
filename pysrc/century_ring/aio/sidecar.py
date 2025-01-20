import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

import anyio
import sniffio

from century_ring.aio.manager import UringIoManager
from century_ring.wrappers import make_io_ring

try:
    from trio.lowlevel import add_instrument, remove_instrument
except ModuleNotFoundError:

    def add_instrument(instrument: Any) -> None:
        pass

    def remove_instrument(instrument: Any) -> None:
        pass


@asynccontextmanager
async def start_uring_sidecar(
    entries: int = 256,
    cq_size: int | None = None,
    sqpoll_idle_ms: int | None = None,
    single_issuer: bool = True,
    autosubmit: bool = True,
    force_submissions: bool = False,
) -> AsyncIterator[UringIoManager]:
    """
    Creates a new :class:`.UringSidecar` and registers it with the event loop.

    This takes identical arguments to :func:`.make_io_ring` with the addition of the
    ``force_submissions`` argument.

    :param force_submissions: Controls if the ring should be submitted on every operation.

        When ``False``, the sidecar will wait for the host event loop to start waiting for I/O
        readiness, meaning that submissions will be batched up. When ``True``, the sidecar will
        force a full submission on every operation
    """

    # gross type hacking because trio keys these by themselves ?_?
    sidecar_instrument: Any | None = None

    with make_io_ring() as ring:
        if (lib := sniffio.current_async_library()) == "trio":
            from century_ring.aio.trio import UringSidecarInstrument

            sidecar_instrument = UringSidecarInstrument(ring)
            add_instrument(sidecar_instrument)

        elif lib == "asyncio":
            # asyncio doesn't have a hook point for waiting for I/O, so instead we have to always
            # enable this.
            force_submissions = True

        async with anyio.create_task_group() as group:
            efd = os.eventfd(0)
            ring.register_eventfd(efd)
            manager = UringIoManager(ring=ring, efd=efd, force_submissions=force_submissions)
            group.start_soon(manager._dispatch_event_results)

            try:
                yield manager
            finally:
                group.cancel_scope.cancel()

                if lib == "trio":
                    remove_instrument(sidecar_instrument)
