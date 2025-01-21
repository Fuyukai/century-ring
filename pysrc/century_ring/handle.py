from __future__ import annotations

import os
from types import TracebackType
from typing import Protocol, Self, final, override

from century_ring._century_ring import CompletionEvent
from century_ring.helpers import raise_for_cqe


class IntoFilelikeHandle(Protocol):
    """
    Protocol for any object that can be turned into a :class:`.FileLikeHandle`.
    """
    
    def as_handle(self) -> FileLikeHandle:
        """
        Converts this object into a :class:`.FileLikeHandle`.
        """

        ...

class FileLikeHandle(IntoFilelikeHandle, Protocol):
    """
    A raw file-like handle.

    This is the underlying method of interaction with the asynchronous ``io_uring`` API; all
    functionality relating to I/O will return one of these and the higher-level code all wraps one
    of these in its own structures.

    "File-like" means that the handle exposes a *file descriptor* that can be read from, written to,
    or polled for readiness like a regular file. In addition, these handles can be closed in an
    idempotent way and used as a context manager. Examples of non-filesystem file-like objects
    include:

    - Sockets
    - Unix pipes
    - ``inotify`` (inode notify) handles
    - `Process ID file descriptors <https://man7.org/linux/man-pages/man2/pidfd_open.2.html>`_
    - Standard input and output

    If you have a handle to one of these objects and wish to convert them to a
    :class:`.FileLikeHandle`, consider using :class:`.FdHandle`.

    .. note::

        The usage of *file-like* has little to nothing to do with the `Python concept`_ of
        file objects or file-like objects. Every :class:`.FileLikeHandle` can be turned into
        a file object, but not every file object can be turned into a :class:`.FileLikeHandle`.

    .. _Python concept: https://docs.python.org/3/glossary.html#term-file-object
    """

    #: The underlying file descriptor for this handle.
    fd: int

    @override
    def as_handle(self) -> Self:
        return self

    def __enter__(self) -> Self: ...

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> bool: ...

    def close_called(self) -> bool:
        """
        Checks if ``close()`` has been called before.

        This method does not keep track or even care if the underlying resource is closed or not,
        as there's no way of knowing. Knowing if ``close()`` has been previously called is enough
        to know if this file-like handle is invalid or not.

        Performing any operations on the ``io_uring`` with this handle if this method returns
        True is invalid.
        """
        ...

    def mark_closed(self) -> None:
        """
        Marks this file-like handle as closed.

        This method is called by the ``io_uring`` when a ``close()`` call is submitted to the loop.
        This does not mean the underlying file descriptor is actually closed, only that an attempt
        to close it has been issued. The file should still be considered closed without performing
        a synchronous close operation to avoid potentially closing a new file descriptor.
        """

        ...

    def close(self) -> None:
        """
        Closes this file-like handle synchronously.

        This method should *always* succeed, even if it raises an exception, as any file descriptor
        `becomes invalid <1>`_ once a call to ``close(2)`` is issued. Likewise, this method must be
        idempotent with subsequent calls doing nothing.

        .. _1: https://stackoverflow.com/a/33114363/15026456
        """

        ...



@final
class FdHandle(FileLikeHandle):
    """
    A :class:`.FileLikeHandle` implementation that simply wraps an integer file descriptor.
    """

    @classmethod
    def from_completion_event(cls, event: CompletionEvent) -> Self:
        """
        Creates a new :class:`.FdHandle` from a :class:`.CompletionEvent`.
        """

        raise_for_cqe(event)
        return cls(event.result)

    def __init__(self, fd: int) -> None:
        self.fd = fd

        self._close_called = False

    @override
    def __enter__(self) -> Self:
        return self

    @override
    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> bool:
        self.close()
        return False

    @override
    def close_called(self) -> bool:
        return self._close_called

    @override
    def mark_closed(self) -> None:
        self._close_called = True

    @override
    def close(self) -> None:
        if self._close_called:
            return

        try:
            os.close(self.fd)
        finally:
            self._close_called = True

    @override
    def __repr__(self):  # pragma: no cover
        return f"FdHandle(fd={self.fd})"
    
    @override
    def __str__(self):  # pragma: no cover
        return str(self.fd)
