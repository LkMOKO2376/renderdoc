API Reference: Performance Counters
===================================

This is the API reference for the functions, classes, and enums in the ``dhr`` module which represents the underlying interface that the UI is built on top of. For more high-level information and instructions on using the python API, see :doc:`../index`.

.. contents:: Sections
   :local:

.. currentmodule:: dhr

Counters
--------

.. autoclass:: dhr.CounterDescription
  :members:

.. autoclass:: dhr.CounterUnit
  :members:

.. autoclass:: dhr.Uuid
  :members:

Counter Types
-------------

.. autoclass:: dhr.GPUCounter
  :members:

.. autofunction:: dhr.IsAMDCounter
.. autofunction:: dhr.IsARMCounter
.. autofunction:: dhr.IsGenericCounter
.. autofunction:: dhr.IsIntelCounter
.. autofunction:: dhr.IsNvidiaCounter
.. autofunction:: dhr.IsVulkanExtendedCounter

Results
-------

.. autoclass:: dhr.CounterResult
  :members:

.. autoclass:: dhr.CounterValue
  :members:
