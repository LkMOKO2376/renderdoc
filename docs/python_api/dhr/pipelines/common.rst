API Reference: Common Pipeline State Abstraction
================================================

This is the API reference for the functions, classes, and enums in the ``dhr`` module which represents the underlying interface that the UI is built on top of. For more high-level information and instructions on using the python API, see :doc:`../../index`.

.. contents:: Sections
   :local:

.. currentmodule:: dhr

.. autoclass:: PipeState
  :members:

General
-------

.. autoclass:: dhr.Offset
  :members:

Vertex Inputs
-------------

.. autoclass:: dhr.BoundVBuffer
  :members:

.. autoclass:: dhr.VertexInputAttribute
  :members:

.. autoclass:: dhr.Topology
  :members:
  
.. autofunction:: dhr.NumVerticesPerPrimitive
.. autofunction:: dhr.VertexOffset
.. autofunction:: dhr.PatchList_Count
.. autofunction:: dhr.PatchList_Topology
.. autofunction:: dhr.IsStrip

Shader Resource Bindings
------------------------

.. autoclass:: dhr.UsedDescriptor
  :members:

.. autoclass:: dhr.BindType
  :members:

.. autoclass:: dhr.TextureSwizzle
  :members:

.. autoclass:: dhr.TextureSwizzle4
  :members:

Samplers
--------

.. autoclass:: dhr.AddressMode
  :members:

.. autoclass:: dhr.TextureFilter
  :members:

.. autoclass:: dhr.FilterMode
  :members:
  
.. autoclass:: dhr.FilterFunction
  :members:

.. autoclass:: dhr.ChromaSampleLocation
  :members:

.. autoclass:: dhr.YcbcrConversion
  :members:

.. autoclass:: dhr.YcbcrRange
  :members:

Viewport and Scissor
--------------------

.. autoclass:: dhr.Viewport
  :members:

.. autoclass:: dhr.Scissor
  :members:

Rasterizer
----------

.. autoclass:: dhr.CullMode
  :members:

.. autoclass:: dhr.DepthBiasMode
  :members:

.. autoclass:: dhr.FillMode
  :members:

.. autoclass:: dhr.ConservativeRaster
  :members:

.. autoclass:: dhr.LineRaster
  :members:

.. autoclass:: dhr.ShadingRateCombiner
  :members:

.. autoclass:: dhr.RasterState
  :members:


Depth and Stencil
-----------------

.. autoclass:: dhr.DepthTestState
  :members:

.. autoclass:: dhr.StencilFace
  :members:

.. autoclass:: dhr.StencilOperation
  :members:

.. autoclass:: dhr.CompareFunction
  :members:

Blending
--------

.. autoclass:: dhr.ColorBlend
  :members:

.. autoclass:: dhr.BlendEquation
  :members:

.. autoclass:: dhr.BlendMultiplier
  :members:

.. autoclass:: dhr.BlendOperation
  :members:

.. autoclass:: dhr.LogicOperation
  :members:

Shader Messages
---------------

.. autoclass:: dhr.ShaderMessage
  :members:

.. autoclass:: dhr.ShaderMessageLocation
  :members:

.. autoclass:: dhr.ShaderMeshMessageLocation
  :members:

.. autoclass:: dhr.ShaderVertexMessageLocation
  :members:

.. autoclass:: dhr.ShaderPixelMessageLocation
  :members:

.. autoclass:: dhr.ShaderGeometryMessageLocation
  :members:

.. autoclass:: dhr.ShaderComputeMessageLocation
  :members:
