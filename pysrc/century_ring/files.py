import enum
import os
from collections.abc import Iterable


class FileOpenMode(enum.Enum):
    """
    Enumeration of the possible ways to open a file.
    """

    #: The file will be opened in read-only mode. Corresponds to ``'r'`` mode in open().
    READ_ONLY = os.O_RDONLY

    #: The file will be opened in write-only mode. Corresponds to ``'w'`` mode in open().
    WRITE_ONLY = os.O_WRONLY

    #: The file will be opened for both reading and writing. Corresponds to ``'r+'`` mode in
    #: open().
    READ_WRITE = os.O_RDWR


class FileOpenFlag(enum.Enum):
    """
    Enumeration of the possible flags to open a file with.
    """

    #: When this flag is provided, data will be written to the end of the file, rather than the
    #: beginning.
    APPEND = enum.auto()  # O_APPEND

    #: When this flag is provided, the file will be created if it does not exist. If the file
    #: already exists, this flag will do nothing.
    CREATE_IF_NOT_EXISTS = enum.auto()  # O_CREAT

    #: When this flag is provided, file will be created, and it must not exist beforehand.
    MUST_CREATE = enum.auto()  # O_CREAT + O_EXCL

    #: When this flag is provided, then the use of kernel-space cache buffers will be avoided.
    DIRECT = enum.auto()  # O_DIRECT

    #: When this flag is provided, opening the file will fail if the file path does not refer to
    #: a directory.
    MUST_BE_DIRECTORY = enum.auto()  # O_DIRECTORY

    #: When this flag is provided, then the file will be opened as a path. Most normal operations
    #: will fail, such as reading or writing, but it can be used as a file handle for opening
    #: other files relative to it.
    PATH = enum.auto()  # O_PATH

    #: When this flag is provided, a best effort is attempted at not editing the access time for
    #: the file.
    NO_ACCESS_TIME = enum.auto()  # O_NOATIME

    #: When this flag is provided, and the trailing part of a file path is a symbolic link, then
    #: the symbolic link will not be followed.
    NO_FOLLOW = enum.auto()  # O_NOFOLLOW

    #: When this flag is provided, the file will be automatically deleted once all references
    #: to it are closed.
    TEMPORARY_FILE = enum.auto()  # O_TMPFILE

    #: When this flag is provided, the file will be truncated to zero bytes before being opened.
    TRUNCATE = enum.auto()  # O_TRUNCATE


def enum_flags_to_int_flags(flags: Iterable[FileOpenFlag]) -> int:
    """
    Converts an enum of :class:`.FileOpenFlag` to integer flags used by open(2) and friends.
    """

    final_flags = os.O_CLOEXEC

    flags = set(flags)

    for flag in flags:
        match flag:
            case FileOpenFlag.APPEND:
                final_flags |= os.O_APPEND

            case FileOpenFlag.CREATE_IF_NOT_EXISTS:
                if FileOpenFlag.TEMPORARY_FILE not in flags:
                    final_flags |= os.O_CREAT

            case FileOpenFlag.MUST_CREATE:
                final_flags |= os.O_EXCL

                if FileOpenFlag.TEMPORARY_FILE not in flags:
                    final_flags |= os.O_CREAT

            case FileOpenFlag.DIRECT:
                final_flags |= os.O_DIRECT | os.O_SYNC

            case FileOpenFlag.MUST_BE_DIRECTORY:
                final_flags |= os.O_DIRECTORY

            case FileOpenFlag.PATH:
                final_flags |= os.O_PATH

            case FileOpenFlag.NO_ACCESS_TIME:
                final_flags |= os.O_NOATIME

            case FileOpenFlag.NO_FOLLOW:
                final_flags |= os.O_NOFOLLOW

            case FileOpenFlag.TEMPORARY_FILE:
                final_flags |= os.O_TMPFILE

            case FileOpenFlag.TRUNCATE:
                final_flags |= os.O_TRUNC

    return final_flags
