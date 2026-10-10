API Reference: Shaders
======================

This is the API reference for the functions, classes, and enums in the ``dhr`` module which represents the underlying interface that the UI is built on top of. For more high-level information and instructions on using the python API, see :doc:`../index`.

.. contents:: Sections
   :local:

.. currentmodule:: dhr

Descriptors
-----------

.. autoclass:: dhr.Descriptor
  :members:

.. autoclass:: dhr.SamplerDescriptor
  :members:

.. autoclass:: dhr.DescriptorFlags
  :members:
   
.. autoclass:: dhr.DescriptorCategory
  :members:
   
.. autoclass:: dhr.DescriptorType
  :members:
   
.. autofunction:: dhr.CategoryForDescriptorType
.. autofunction:: dhr.IsConstantBlockDescriptor
.. autofunction:: dhr.IsReadOnlyDescriptor
.. autofunction:: dhr.IsReadWriteDescriptor
.. autofunction:: dhr.IsSamplerDescriptor

.. autoclass:: dhr.DescriptorLogicalLocation
  :members:

.. autoclass:: dhr.DescriptorRange
  :members:

.. autoclass:: dhr.DescriptorAccess
  :members:

Reflection
----------

.. autoclass:: dhr.ShaderReflection
  :members:

.. autoclass:: dhr.ShaderStage
  :members:

.. autoclass:: dhr.ShaderStageMask
  :members:

.. autofunction:: dhr.MaskForStage
.. autofunction:: dhr.FirstStageForMask

.. autoclass:: dhr.SigParameter
  :members:

.. autoclass:: dhr.ShaderBuiltin
  :members:

.. autoclass:: dhr.ConstantBlock
  :members:

.. autoclass:: dhr.ShaderSampler
  :members:

.. autoclass:: dhr.ShaderResource
  :members:

Debug Info
----------

.. autoclass:: dhr.ShaderDebugInfo
  :members:

.. autoclass:: dhr.ShaderEncoding
  :members:
  
.. autoclass:: dhr.KnownShaderTool
  :members:
  
.. autofunction:: dhr.ToolExecutable
.. autofunction:: dhr.ToolInput
.. autofunction:: dhr.ToolOutput

.. autofunction:: dhr.IsTextRepresentation

.. autoclass:: dhr.ShaderEntryPoint
  :members:

.. autoclass:: dhr.ShaderSourceFile
  :members:

.. autoclass:: dhr.ShaderCompileFlags
  :members:

.. autoclass:: dhr.ShaderCompileFlag
  :members:

.. autoclass:: dhr.ShaderSourcePrefix
  :members:

Shader Constants
----------------

.. autoclass:: dhr.ShaderConstant
  :members:

.. autoclass:: dhr.ShaderConstantType
  :members:

.. autoclass:: dhr.ShaderVariableFlags
  :members:

.. autoclass:: dhr.VarType
  :members:

.. autofunction:: dhr.VarTypeByteSize
.. autofunction:: dhr.VarTypeCompType

Shader Debugging
----------------

.. autoclass:: dhr.ShaderDebugTrace
  :members:

.. autoclass:: dhr.ShaderDebugger
  :members:

.. autoclass:: dhr.SourceVariableMapping
  :members:

.. autoclass:: dhr.DebugVariableReference
  :members:

.. autoclass:: dhr.DebugVariableType
  :members:

.. autoclass:: dhr.LineColumnInfo
  :members:

.. autoclass:: dhr.InstructionSourceInfo
  :members:

.. autoclass:: dhr.ShaderDebugState
  :members:

.. autoclass:: dhr.ShaderEvents
  :members:

.. autoclass:: dhr.ShaderVariableChange
  :members:

Shader Variables
----------------
  
.. autoclass:: dhr.ShaderVariable
  :members:

.. autoclass:: dhr.ShaderValue
  :members:

.. autoclass:: dhr.PointerVal
  :members:

.. autoclass:: dhr.ShaderBindIndex
  :members:

.. autoclass:: dhr.ShaderDirectAccess
  :members:
