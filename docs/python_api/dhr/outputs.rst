API Reference: Replay Outputs
=============================

This is the API reference for the functions, classes, and enums in the ``dhr`` module which represents the underlying interface that the UI is built on top of. For more high-level information and instructions on using the python API, see :doc:`../index`.

.. contents:: Sections
   :local:

.. currentmodule:: dhr

General
-------

.. autoclass:: ReplayOutput
  :members:

.. autoclass:: ReplayOutputType
  :members:

.. autofunction:: dhr.SetColors

Window Configuration
--------------------

.. autoclass:: WindowingData
  :members:

.. autoclass:: WindowingSystem
  :members:

.. autofunction:: dhr.CreateHeadlessWindowingData
.. autofunction:: dhr.CreateWin32WindowingData
.. autofunction:: dhr.CreateXlibWindowingData
.. autofunction:: dhr.CreateXCBWindowingData
.. autofunction:: dhr.CreateWaylandWindowingData
.. autofunction:: dhr.CreateAndroidWindowingData
.. autofunction:: dhr.CreateMacOSWindowingData

Texture View
------------

.. autoclass:: TextureDisplay
  :members:

.. autoclass:: DebugOverlay
  :members:

Mesh View
---------

.. autoclass:: MeshDisplay
  :members:

.. autoclass:: MeshDataStage
  :members:

.. autoclass:: MeshletSize
  :members:

.. autoclass:: TaskGroupSize
  :members:

.. autoclass:: MeshFormat
  :members:

.. autoclass:: Visualisation
  :members:

.. autoclass:: Camera
  :members:

.. autoclass:: CameraType
  :members:

.. autoclass:: AxisMapping
  :members:

.. autofunction:: dhr.InitCamera
