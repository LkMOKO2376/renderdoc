API Reference: qdhr Main Interfaces
=========================================

This is the API reference for the functions, classes, and enums in the ``qdhr`` module which represents the UI-specific interface for integrating with the UI and writing UI extensions. For more high-level information and instructions on using the python API, see :doc:`../index` and :doc:`../ui_extensions`.

.. contents:: Sections
   :local:

.. module:: qdhr

Context
-------

.. autoclass:: qdhr.CaptureContext
  :members:

Replay Manager
--------------

.. autoclass:: qdhr.ReplayManager
  :members:

RGP Interop Control
-------------------

.. autoclass:: qdhr.RGPInterop
  :members:


CaptureViewer Interface
------------------------

.. autoclass:: qdhr.CaptureViewer
  :members:

Helpers
-------

.. autoclass:: qdhr.BufferInterpreter
  :members:

.. autoclass:: qdhr.PackingRules
  :members:

.. autoclass:: qdhr.ParsedBufferFormat
  :members:

.. autoclass:: qdhr.ParseError
  :members:

Utilities
---------

.. autoclass:: qdhr.DockReference
  :members:
  :exclude-members: enum_constants__, 

.. autoclass:: qdhr.CaptureModifications
  :members:
  :exclude-members: enum_constants__, 

.. autoclass:: qdhr.CaptureSettings
  :members:

.. autoclass:: qdhr.EventBookmark
  :members:

