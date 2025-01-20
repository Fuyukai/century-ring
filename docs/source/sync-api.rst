.. _sync-api:

Low-level API
=============

Century Ring provides low-level synchronous bindings to an ``io_uring`` that can be used e.g. for
creating an event loop. 

Creating the ``io_uring``
-------------------------

Creating a new ``io_uring`` can be done with :func:`make_io_ring`:

.. autofunction:: century_ring.make_io_ring

As this is a context manager, attempting to access the ring after it is closed will fail:

.. code-block:: python

    with make_io_ring() as ring:
        ...

    ring.prep_openat(...)  # will fail with ValueError: The ring is closed


Submitting operations
---------------------

New operations can be added to the submission queue with the various wrapper functions on
:class:`.IoUring`. 

File I/O
~~~~~~~~

.. automethod:: century_ring.IoUring.prep_openat

.. autoclass:: century_ring.FileOpenFlag
    :members:

.. autoclass:: century_ring.FileOpenMode
    :members:

.. automethod:: century_ring.IoUring.prep_read

.. automethod:: century_ring.IoUring.prep_write

Network I/O
~~~~~~~~~~~

.. automethod:: century_ring.IoUring.prep_create_socket

.. automethod:: century_ring.IoUring.prep_connect_v4

.. automethod:: century_ring.IoUring.prep_connect_v6

.. automethod:: century_ring.IoUring.prep_send

.. automethod:: century_ring.IoUring.prep_recv

Shared/misc
~~~~~~~~~~~

.. automethod:: century_ring.IoUring.prep_close

Submitting and reaping completions
----------------------------------

There are three methods for submitting the event loop, depending on if you need to wait:

.. automethod:: century_ring.IoUring.submit

.. automethod:: century_ring.IoUring.submit_and_wait

.. automethod:: century_ring.IoUring.submit_and_wait_with_timeout

Once submitted, completion events can be reaped with :meth:`IoUring.get_completion_entries`.

.. automethod:: century_ring.IoUring.get_completion_entries

.. autoclass:: century_ring.CompletionEvent
    :members:

.. autofunction:: century_ring.raise_for_cqe

SQE flags
---------

Submission queue entires can have flags associated with them which control specific behaviour; all
submission preparation methods take a ``sqe_flags`` parameter that control these flags. This is
an opaque bitfield that is produced from :func:`century_ring.make_sqe_flags`.

.. autofunction:: century_ring.make_sqe_flags
