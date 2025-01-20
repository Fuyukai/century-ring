import os

import anyio
import anyio.lowlevel
import attr
from anyio.streams.memory import MemoryObjectSendStream

from century_ring import raise_for_cqe
from century_ring._century_ring import CompletionEvent
from century_ring.wrappers import IoUring


@attr.define(slots=True, kw_only=True)
class UringIoManager:
    """
    An alternative I/O manager that uses ``io_uring`` as the underlying event driver.

    This only supports running as a secondary loop currently, using an ``eventfd`` and a separate
    task on the main selector-based event loop to wake up the waiting task and dispatch events
    to sleeping tasks.
    """

    ring: IoUring = attr.field()
    efd: int = attr.field()
    _force_submissions: bool = attr.field(init=True, alias="force_submissions")

    _completion_waiters: dict[int, MemoryObjectSendStream[CompletionEvent]] = attr.field(
        factory=dict
    )

    # Internal functions
    async def _dispatch_event_results(self):
        """
        Listens on the eventfd and dispatches event completions.
        """

        while True:
            await anyio.wait_readable(self.efd)
            # discarded, we don't actually care what it says.
            os.read(self.efd, 8)

            for dispatched in self.ring.get_completion_entries():
                if dispatched.should_be_ignored():
                    continue

                waiter = self._completion_waiters.pop(dispatched.user_data, None)
                if waiter is None:  # pragma: no cover
                    # oh well
                    continue

                try:
                    waiter.send_nowait(dispatched)
                except (anyio.WouldBlock, anyio.BrokenResourceError):  # pragma: no cover
                    # whatever, nobody's listening anyway
                    continue
                else:
                    waiter.close()

    # Public API
    async def wait_for_completion(
        self, user_data: int, *, autoraise: bool = True
    ) -> CompletionEvent:
        """
        Waits for a single completion with the specified ``user_data``.

        This function *is* cancellable, but it will cause the completion event to be sent into
        the void rather than cancelling it on the ``io_uring`` side.

        If ``force_submissions`` was provided when creating this manager, then this function will
        submit all submission queue entries before suspending.

        For obvious reasons, if the submission event had the ``skip_success`` flag enabled, this
        function will never work. Please do not use this function for submission events with the
        ``skip_success`` flag enabled.

        :param user_data: A ``user_data`` value returned from a submission queue function.
        :param autoraise: If True, then this will automatically raise if the CQE returns an error.
        :return: The posted completion event.
        """

        # TODO: make SQE functions return a SubmissionEntry that has the flags defined, then
        #       pass it to this function to prevent passing one with IOSQE_CQE_SKIP_SUCCESS.

        if self._force_submissions:
            self.ring.submit()

        send, recv = anyio.create_memory_object_stream[CompletionEvent]()
        self._completion_waiters[user_data] = send

        async with recv:
            cqe = await recv.receive()
            if autoraise:
                raise_for_cqe(cqe)

            return cqe
