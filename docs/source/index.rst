.. Century Ring documentation master file, created by
   sphinx-quickstart on Thu Jan 16 17:27:45 2025.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

Century Ring
============

Century Ring is a Python binding to the ``io_uring`` subsystem on Linux 5.18+. Century Ring
provides two APIs: a synchronous one that is ideal for writing your own event loops, and an 
asynchronous one that integrates with `AnyIO`_ and `Trio`_.


.. toctree::
   :maxdepth: 2
   :caption: Contents:

   uring_concepts.rst
   sync-api.rst


.. _AnyIO: https://anyio.readthedocs.io/en/stable/index.html
.. _Trio: https://trio.readthedocs.io/en/stable/index.html
