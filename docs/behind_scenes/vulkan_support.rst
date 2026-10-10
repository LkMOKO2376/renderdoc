Vulkan Support
==============

This page documents the support of Vulkan in DHR. This gives an overview of what DHR is capable of, and primarily lists information that is relevant. You might also be interested in the :doc:`full list of features <../getting_started/features>`.

Vulkan capture
--------------

DHR's Vulkan support uses the sophisticated layering mechanism built into the Vulkan API. This means that once DHR has registered its capture layers, there is no need for invasive process hooking - we can simply launch the target process with an environment variable set.


The one requirement of this however is that the layer does need to be registered in an OS specific way - on windows this is in the registry, on linux this is in ``/usr/share/vulkan/implicit_layer.d``, ``/etc/vulkan/implicit_layer.d``, or ``$HOME/.local/share/vulkan/implicit_layer.d``. That way the Vulkan loader can scan and initialise the layer.


Usually this will happen for you if you install DHR with a proper installer, or update from a previous version. However if you are compiling DHR yourself or running a loose unzipped build, the capture panel will show a warning indicating that the layers need to be registered. Just click this and the registration will be applied.


.. figure:: ../imgs/Screenshots/LayerRegistration.png

    Vulkan Layer Registration

Performance notes
-----------------

Vulkan is intended as a high-performance low CPU overhead API, and DHR strives to maintain that performance contract at a reasonable level. While some overhead is inevitable DHR aims to have no locks on the 'hot path' of command buffer recording, minimal or no allocation, and in general to have low performance overhead while not capturing.

Some patterns of access are more or less conducive to good performance on DHR, so if you are having trouble with slow capture, large memory/disk overhead or slow replay you might want to try eliminating use of persistent maps of memory from coherent heaps by mapping and unmapping them around changes, or reduce the number of submits you make while you have coherent memory persistently mapped.

Likewise try to avoid making very large memory allocations in the range of 1GB and above. By its nature DHR must save one or more copies of memory allocations to enable proper capture, so having allocations limited to only a few 100s of megabytes can help gain granularity of management and limit the memory overhead DHR adds. There may be optimisation of this in future on DHR's side but there are no easy guarantees.

Current support
---------------

DHR has support for Vulkan version 1.4, as well as a number of extensions, but it contains some caveats. In addition, not all replay features are currently supported, but this is being actively worked on.

* DHR assumes that even if multiple GPUs are present, that only one VkDevice will be created and used.
* DHR captures will in general not be portable between different systems, only currently supporting capture and replay on the same or similar enough machines.

For more information about DHR's raytracing support see :doc:`raytracing`. Note that raytracing support is limited on nvidia drivers due to missing driver functionality.

Android
-------

Vulkan capture and replay on Android is natively supported. For more information on how to capture with Android see :doc:`../how/how_android_capture`.

See Also
--------

* :doc:`../getting_started/features`
