from __future__ import annotations

import os
from types import TracebackType
from typing import Self

import attr


@attr.define(slots=True)
class AutoclosingScope:
    """
    Automatically closes the provided FDs on scope exit.
    """

    fds: list[int] = attr.field(factory=list)

    def add(self, fd: int) -> int:
        self.fds.append(fd)
        return fd

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self, exc: type[BaseException] | None, val: BaseException | None, tb: TracebackType | None
    ) -> bool:
        excs: list[Exception] = []

        for fd in self.fds:
            try:
                os.close(fd)
            except Exception as e:
                excs.append(e)

        if excs:
            raise ExceptionGroup("Failure closing some fds", excs) from val

        return False
