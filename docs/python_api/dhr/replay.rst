API Reference: Replay Control
=============================

This is the API reference for the functions, classes, and enums in the ``dhr`` module which represents the underlying interface that the UI is built on top of. For more high-level information and instructions on using the python API, see :doc:`../index`.

.. contents:: Sections
   :local:

.. currentmodule:: dhr

Initialisation and Shutdown
---------------------------

.. autofunction:: dhr.InitialiseReplay
.. autofunction:: dhr.ShutdownReplay

.. autoclass:: dhr.GlobalEnvironment
  :members:

.. autoclass:: dhr.ResultCode
  :members:

.. autoclass:: dhr.ResultDetails
  :members:

Capture File Access
-------------------

.. autofunction:: dhr.OpenCaptureFile

.. autoclass:: dhr.CaptureAccess
  :members:

.. autoclass:: dhr.CaptureFile
  :members:

.. autoclass:: dhr.ReplaySupport
  :members:

.. autoclass:: dhr.CaptureFileFormat
  :members:

.. autoclass:: dhr.SectionProperties
  :members:

.. autoclass:: dhr.SectionType
  :members:

.. autoclass:: dhr.SectionFlags
  :members:

.. autoclass:: dhr.Thumbnail
  :members:

GPU Enumeration
---------------

.. autoclass:: dhr.GPUDevice
  :members:

.. autoclass:: dhr.GPUVendor
  :members:

.. autofunction:: dhr.GPUVendorFromPCIVendor

.. autoclass:: dhr.GraphicsAPI
  :members:

.. autofunction:: dhr.IsD3D

.. autofunction:: dhr.GetDriverInformation

.. autoclass:: dhr.DriverInformation
  :members:

Replay Controller
-----------------

.. autoclass:: dhr.ReplayController
  :members:

.. autoclass:: dhr.ReplayOptions
  :members:

.. autoclass:: dhr.ReplayOptimisationLevel
  :members:

.. autoclass:: dhr.APIProperties
  :members:

Device Protocols
----------------

.. autoclass:: dhr.DeviceProtocolController
  :members:

.. autofunction:: dhr.GetSupportedDeviceProtocols
.. autofunction:: dhr.GetDeviceProtocolController

Remote Servers
--------------

.. autoclass:: dhr.RemoteServer
  :members:

.. autofunction:: dhr.CreateRemoteServerConnection
.. autofunction:: dhr.CheckRemoteServerConnection
.. autofunction:: dhr.BecomeRemoteServer

.. autoclass:: dhr.PathEntry
  :members:

.. autoclass:: dhr.PathProperty
  :members:
