Century Ring
============

`Century Ring <https://www.youtube.com/watch?v=ccTGW5ckxeQ>`_ is a Python binding to the Tokio
``io_uring`` library. 

Example
-------

A basic example of writing to and reading from a temporary file. Obviously in the real world you
would want to have better error handling and simultaneous tasks, but this shows the basic flow of
how to use the uring.

.. code-block:: python

    import os

    from century_ring import make_io_ring, raise_for_cqe
    from century_ring.files import FileOpenFlag, FileOpenMode

    with make_io_ring() as ring:
        ring.prep_openat(None, b"/tmp", FileOpenMode.READ_WRITE, flags={FileOpenFlag.TEMPORARY_FILE})
        ring.submit_and_wait()
        raw_cqe = ring.get_completion_entries()[0]
        raise_for_cqe(raw_cqe)
        open_fd = raw_cqe.result

        ring.prep_write(open_fd, b"wow!")
        ring.submit_and_wait()
        raise_for_cqe(ring.get_completion_entries()[0])

        ring.prep_read(open_fd, 4096, offset=0)
        ring.submit_and_wait()
        read_cqe = ring.get_completion_entries()[0]
        raise_for_cqe(read_cqe)

        buffer = read_cqe.buffer

        assert buffer is not None
        assert buffer == b"wow!"
        print(buffer)

        os.close(open_fd)
