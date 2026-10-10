API Reference: Utilities
========================

This is the API reference for the functions, classes, and enums in the ``dhr`` module which represents the underlying interface that the UI is built on top of. For more high-level information and instructions on using the python API, see :doc:`../index`.

.. contents:: Sections
   :local:

.. currentmodule:: dhr

Maths
-----

.. autoclass:: FloatVector
  :members:

.. autofunction:: dhr.HalfToFloat
.. autofunction:: dhr.FloatToHalf

Logging & Versioning
--------------------

.. autofunction:: dhr.LogMessage
.. autofunction:: dhr.SetDebugLogFile
.. autofunction:: dhr.GetLogFile
.. autofunction:: dhr.GetCurrentProcessMemoryUsage
.. autofunction:: dhr.DumpObject

.. autoclass:: LogType
  :members:


Versioning
----------

.. autofunction:: dhr.GetVersionString
.. autofunction:: dhr.GetCommitHash
.. autofunction:: dhr.IsReleaseBuild

Settings
--------

.. autofunction:: dhr.GetConfigSetting
.. autofunction:: dhr.SetConfigSetting
.. autofunction:: dhr.SaveConfigSettings

Self-hosted captures
--------------------

.. autofunction:: dhr.CanSelfHostedCapture
.. autofunction:: dhr.StartSelfHostCapture
.. autofunction:: dhr.EndSelfHostCapture
