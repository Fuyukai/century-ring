import os
import socket
import stat

import attr
import pytest

from century_ring import raise_for_cqe
from century_ring.wrappers import make_io_ring
from tests import AutoclosingScope


@attr.define(slots=True, kw_only=True)
class ListenSocket:
    sock: socket.socket = attr.field()
    address: str = attr.field()
    port: int = attr.field()


@pytest.fixture
def listening_tcp_v4():
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    sock.bind(("127.0.0.1", 0))
    sock.listen(1)

    port: int = sock.getsockname()[1]

    with sock:
        yield ListenSocket(sock=sock, address="127.0.0.1", port=port)


def test_create_socket():
    with make_io_ring() as ring, AutoclosingScope() as scope:
        ring.prep_create_socket(socket.AF_INET, socket.SOCK_STREAM)
        ring.submit_and_wait()
        cqe = ring.get_completion_entries()[0]
        raise_for_cqe(cqe)

        fd = scope.add(cqe.result)

        fstat = os.fstat(fd)
        assert stat.S_ISSOCK(fstat.st_mode)


def test_socket_connect(listening_tcp_v4: ListenSocket):
    with make_io_ring() as ring, AutoclosingScope() as scope:
        our_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        scope.add(our_socket.fileno())

        ring.prep_connect_v4(our_socket.fileno(), listening_tcp_v4.address, listening_tcp_v4.port)
        ring.submit_and_wait()
        cqe = ring.get_completion_entries()[0]
        raise_for_cqe(cqe)

        assert our_socket.getpeername() == (listening_tcp_v4.address, listening_tcp_v4.port)


def test_socket_uring_write(listening_tcp_v4: ListenSocket):
    with make_io_ring() as ring, AutoclosingScope() as scope:
        our_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        scope.add(our_socket.fileno())

        our_socket.connect((listening_tcp_v4.address, listening_tcp_v4.port))
        inbound_socket, _ = listening_tcp_v4.sock.accept()
        our_socket.setsockopt(socket.SOL_TCP, socket.TCP_NODELAY, 1)

        ring.prep_send(our_socket.fileno(), b"test!")
        ring.submit()

        data = inbound_socket.recv(2048, socket.SOCK_NONBLOCK)
        assert data == b"test!"
        ring.submit_and_wait()
        cqe = ring.get_completion_entries()[0]
        raise_for_cqe(cqe)

        assert cqe.result == len(data)


def test_socket_uring_read(listening_tcp_v4: ListenSocket):
    with make_io_ring() as ring, AutoclosingScope() as scope:
        our_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        scope.add(our_socket.fileno())

        our_socket.connect((listening_tcp_v4.address, listening_tcp_v4.port))
        inbound_socket, _ = listening_tcp_v4.sock.accept()
        our_socket.setsockopt(socket.SOL_TCP, socket.TCP_NODELAY, 1)

        ring.prep_recv(our_socket.fileno(), 2048)
        ring.submit()

        inbound_socket.send(b"test!", socket.SOCK_NONBLOCK)
        ring.submit_and_wait()
        cqe = ring.get_completion_entries()[0]
        raise_for_cqe(cqe)

        assert cqe.buffer == b"test!"
