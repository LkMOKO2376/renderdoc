API Reference: Structured Data
==============================

This is the API reference for the functions, classes, and enums in the ``dhr`` module which represents the underlying interface that the UI is built on top of. For more high-level information and instructions on using the python API, see :doc:`../index`.

.. contents:: Sections
   :local:

.. currentmodule:: dhr

Type information
----------------

.. autoclass:: SDType
  :members:

.. autoclass:: SDBasic
  :members:

.. autoclass:: SDTypeFlags
  :members:

Objects
-------

.. autoclass:: SDObject
  :members:

.. autoclass:: SDObjectData
  :members:

.. autoclass:: SDObjectPODData
  :members:

Chunks
------

.. autoclass:: SDChunk
  :members:

.. autoclass:: SDChunkMetaData
  :members:

.. autoclass:: SDChunkFlags
  :members:

Structured File
---------------

.. autoclass:: SDFile
  :members:

Creation Helper Functions
-------------------------

.. autofunction:: dhr.makeSDArray
.. autofunction:: dhr.makeSDBool
.. autofunction:: dhr.makeSDEnum
.. autofunction:: dhr.makeSDFloat
.. autofunction:: dhr.makeSDInt32
.. autofunction:: dhr.makeSDInt64
.. autofunction:: dhr.makeSDResourceId
.. autofunction:: dhr.makeSDString
.. autofunction:: dhr.makeSDStruct
.. autofunction:: dhr.makeSDUInt32
.. autofunction:: dhr.makeSDUInt64
