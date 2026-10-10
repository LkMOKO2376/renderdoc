API Reference: Capturing
========================

This is the API reference for the functions, classes, and enums in the ``dhr`` module which represents the underlying interface that the UI is built on top of. For more high-level information and instructions on using the python API, see :doc:`../index`.

.. contents:: Sections
   :local:

.. currentmodule:: dhr

Execution & Injection
---------------------

.. autofunction:: dhr.ExecuteAndInject
.. autofunction:: dhr.InjectIntoProcess

.. autoclass:: dhr.CaptureOptions
  :members:
  
.. autoclass:: dhr.EnvironmentModification
  :members:

.. autoclass:: dhr.EnvMod
  :members:

.. autoclass:: dhr.EnvSep
  :members:

.. autoclass:: dhr.ExecuteResult
  :members:

Global Hooking
--------------

.. autofunction:: dhr.StartGlobalHook
.. autofunction:: dhr.StopGlobalHook
.. autofunction:: dhr.IsGlobalHookActive
.. autofunction:: dhr.CanGlobalHook

Target Control
--------------

.. autofunction:: dhr.EnumerateRemoteTargets
.. autofunction:: dhr.CreateTargetControl

.. autoclass:: dhr.TargetControl
  :members:

.. autoclass:: dhr.TargetControlMessage
  :members:

.. autoclass:: dhr.TargetControlMessageType
  :members:

.. autoclass:: dhr.NewCaptureData
  :members:

.. autoclass:: dhr.APIUseData
  :members:

.. autoclass:: dhr.BusyData
  :members:

.. autoclass:: dhr.NewChildData
  :members:

