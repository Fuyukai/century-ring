from typing import Any, override

import attr
from trio.abc import Instrument

from century_ring.ring import IoUring


@attr.define(frozen=True, slots=True, hash=False)
class UringSidecarInstrument(Instrument):
    """
    A :class:`trio.abc.Instrument` that is used for implementing the ``io_uring`` sidecar.
    """

    ring: IoUring = attr.field()

    @override
    def __hash__(self):
        # iouring type isn't hashable
        return id(self)

    @override
    def before_io_wait(self, *args: Any, **kwargs: Any):
        self.ring.submit()
