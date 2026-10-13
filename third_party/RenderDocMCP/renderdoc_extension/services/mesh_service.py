"""
Mesh layout service for RenderDoc.

Reports the vertex-input layout of a draw: the input-assembly topology, the
bound vertex and index buffers, the vertex attribute declarations, and a flat
list of "suggested columns" (one token per attribute component) that a caller
can pick from when deciding what to export.
"""

import base64
import struct

import dhr as rd

# Component suffix ordering used for the suggested column tokens.
_COMPONENT_LETTERS = "xyzw"

# struct format character for each supported index width, in bytes.
_INDEX_STRUCT_TYPES = {1: "B", 2: "H", 4: "I"}

# Don't try to scan absurdly large index ranges just to find a vertex count.
_MAX_INDEX_SCAN_BYTES = 64 * 1024 * 1024

# Upper bound on a vertex/index stream we are willing to read in one go. Also
# guards against the sentinel byte_size (whole-buffer) values some APIs report.
_MAX_STREAM_BYTES = 256 * 1024 * 1024


class MeshService:
    """Mesh / vertex-input layout service"""

    def __init__(self, ctx, invoke_fn):
        self.ctx = ctx
        self._invoke = invoke_fn

    def get_mesh_layout(self, event_id):
        """Get the vertex-input layout of the draw at an event"""
        if not self.ctx.IsCaptureLoaded():
            raise ValueError("No capture loaded")

        result = {"layout": None}

        def callback(controller):
            layout, _vbuffers, _ib = self._build_layout(controller, event_id)
            result["layout"] = layout

        self._invoke(callback)
        return result["layout"]

    def get_mesh_data(self, event_id):
        """Get the raw vertex and index bytes of the draw at an event.

        Returns the layout (as get_mesh_layout does) plus the raw bytes of each
        distinct vertex stream and the index stream, base64-encoded. Decoding
        is deliberately left to the client: reloading this extension requires
        restarting the DHR GUI, so the less logic lives here the better.
        """
        if not self.ctx.IsCaptureLoaded():
            raise ValueError("No capture loaded")

        result = {"mesh": None}

        def callback(controller):
            layout, vbuffers, ib = self._build_layout(controller, event_id)

            mesh = {
                "layout": layout,
                "vertex_streams": [],
                "index_stream": None,
            }

            num_vertices = layout.get("num_vertices")

            # One entry per distinct (resource_id, byte_offset, byte_stride).
            seen = set()
            for slot, vb in vbuffers:
                # Skip unbound slots: GetVBuffers() always emits every slot.
                if vb.resourceId == rd.ResourceId.Null():
                    continue
                # Stride 0 means no real data is bound -- the attribute is fed
                # from a generic/constant value. Never try to read it.
                if vb.byteStride == 0:
                    continue

                key = (str(vb.resourceId), vb.byteOffset, vb.byteStride)
                if key in seen:
                    continue
                seen.add(key)

                stream = {
                    "slot": slot,
                    "resource_id": str(vb.resourceId),
                    "byte_offset": vb.byteOffset,
                    "byte_stride": vb.byteStride,
                    "byte_length": None,
                    "data_base64": None,
                }

                self._read_stream(
                    controller, stream, vb.resourceId, vb.byteOffset,
                    vb.byteStride, num_vertices,
                )

                mesh["vertex_streams"].append(stream)

            # Index stream. byte_offset must include the draw's index_offset
            # bias; byte_length is num_indices * stride.
            try:
                indexed = ib is not None and ib.resourceId != rd.ResourceId.Null() \
                    and ib.byteStride != 0
            except Exception:
                indexed = False

            if indexed:
                action = None
                try:
                    action = self.ctx.GetAction(event_id)
                except Exception:
                    action = None

                index_offset = action.indexOffset if action is not None else 0
                index_stream = {
                    "resource_id": str(ib.resourceId),
                    "byte_offset": ib.byteOffset + index_offset * ib.byteStride,
                    "byte_stride": ib.byteStride,
                    "byte_length": None,
                    "data_base64": None,
                }

                self._read_stream(
                    controller, index_stream, ib.resourceId, index_stream["byte_offset"],
                    ib.byteStride, layout.get("num_indices"),
                )

                mesh["index_stream"] = index_stream

            result["mesh"] = mesh

        self._invoke(callback)
        return result["mesh"]

    def _read_stream(self, controller, stream, resource_id, byte_offset, byte_stride, count):
        """Size and read one stream, recording an error rather than guessing.

        byte_length is always byte_stride * count. The bound byte_size field is
        NOT trusted: on Vulkan it comes back as the sentinel 0xFFFFFFFF
        (whole buffer), which would read the wrong range.
        """
        if count is None or count <= 0:
            stream["error"] = "element count unavailable; cannot size stream"
            return

        byte_length = byte_stride * count
        if byte_length <= 0 or byte_length > _MAX_STREAM_BYTES:
            stream["error"] = "refusing to read %d bytes (stride %d x %s elements)" % (
                byte_length,
                byte_stride,
                count,
            )
            return

        stream["byte_length"] = byte_length
        try:
            data = controller.GetBufferData(resource_id, byte_offset, byte_length)
        except Exception as e:
            stream["error"] = "Failed to read stream: %s" % str(e)
            return

        stream["data_base64"] = base64.b64encode(data).decode("ascii")

    def _build_layout(self, controller, event_id):
        """Build the vertex-input layout.

        Shared by get_mesh_layout and get_mesh_data so the two never drift.
        Returns (layout, vbuffers, ib) where vbuffers is a list of
        (slot, BoundVBuffer) pairs and ib is the live index-buffer BoundVBuffer
        (or None when it could not be queried).
        """
        controller.SetFrameEvent(event_id, True)

        pipe = controller.GetPipelineState()

        layout = {
            "event_id": event_id,
            "input_assembly_topology": None,
            "vertex_buffers": [],
            "index_buffer": None,
            "attributes": [],
            "num_indices": None,
            "num_vertices": None,
            "suggested_columns": [],
        }

        # Primitive topology. On this build the IA state is exposed directly
        # as the current primitive topology (there is no GetIAState()).
        try:
            layout["input_assembly_topology"] = str(pipe.GetPrimitiveTopology())
        except Exception as e:
            layout["topology_error"] = str(e)

        # Vertex buffer bindings.
        vbuffers = []
        try:
            for slot, vb in enumerate(pipe.GetVBuffers()):
                vbuffers.append((slot, vb))
                layout["vertex_buffers"].append(
                    {
                        "slot": slot,
                        "resource_id": str(vb.resourceId),
                        "byte_offset": vb.byteOffset,
                        "byte_stride": vb.byteStride,
                        "byte_size": vb.byteSize,
                    }
                )
        except Exception as e:
            layout["vertex_buffers_error"] = str(e)

        # Index buffer binding. GetIBuffer() returns a BoundVBuffer for the
        # index buffer; a null resource and zero stride mean a non-indexed
        # draw.
        ib = None
        try:
            ib = pipe.GetIBuffer()
            indexed = ib.resourceId != rd.ResourceId.Null() and ib.byteStride != 0
            layout["index_buffer"] = {
                "resource_id": str(ib.resourceId),
                "byte_offset": ib.byteOffset,
                "byte_stride": ib.byteStride,
                "byte_size": ib.byteSize,
                "indexed": indexed,
            }
        except Exception as e:
            layout["index_buffer_error"] = str(e)

        # Vertex attributes feeding the vertex shader.
        try:
            for attr in pipe.GetVertexInputs():
                layout["attributes"].append(self._serialize_attribute(attr))
        except Exception as e:
            layout["attributes_error"] = str(e)

        # The flat, name-ordered list of columns the user can choose from.
        layout["suggested_columns"] = self._suggest_columns(layout["attributes"])

        # Index / vertex counts, derived from the action where possible.
        self._add_counts(controller, event_id, layout, ib)

        return layout, vbuffers, ib

    def _serialize_attribute(self, attr):
        """Serialize a single VertexInputAttribute"""
        attribute = {
            "name": attr.name,
            "vertex_buffer": attr.vertexBuffer,
            "byte_offset": attr.byteOffset,
            "per_instance": attr.perInstance,
            "instance_rate": attr.instanceRate,
            "used": attr.used,
            # A generic (stride-0) attribute reads from genericValue rather than
            # a vertex buffer; genericEnabled says which it is.
            "generic_enabled": getattr(attr, "genericEnabled", False),
            "generic_value": self._serialize_pixel_value(attr.genericValue),
        }
        attribute.update(self._decompose_format(attr.format))
        return attribute

    def _serialize_pixel_value(self, value):
        """Serialize a PixelValue union to float/int component lists"""
        out = {}
        try:
            out["float"] = list(value.floatValue[:4])
        except Exception:
            pass
        try:
            out["uint"] = list(value.uintValue[:4])
        except Exception:
            pass
        try:
            out["int"] = list(value.intValue[:4])
        except Exception:
            pass
        return out

    def _decompose_format(self, fmt):
        """Turn a ResourceFormat into readable fields"""
        comp_type = fmt.compType

        try:
            format_name = fmt.Name()
        except Exception:
            format_name = ""

        return {
            "format_name": format_name,
            "comp_count": fmt.compCount,
            "comp_type": str(comp_type),
            "comp_byte_width": fmt.compByteWidth,
            "is_normalized": comp_type
            in (rd.CompType.UNorm, rd.CompType.SNorm, rd.CompType.UNormSRGB),
            "is_integer": comp_type
            in (
                rd.CompType.UInt,
                rd.CompType.SInt,
                rd.CompType.UScaled,
                rd.CompType.SScaled,
            ),
            "is_float": comp_type == rd.CompType.Float,
        }

    def _suggest_columns(self, attributes):
        """Build the flat list of column tokens offered to the user"""
        columns = []
        for index, attr in enumerate(attributes):
            name = attr["name"] or ("attr%d" % index)
            count = attr["comp_count"] or 0
            if count <= 0:
                continue
            for letter in _COMPONENT_LETTERS[:count]:
                columns.append("%s.%s" % (name, letter))
        return columns

    def _add_counts(self, controller, event_id, layout, ib):
        """Fill in num_indices / num_vertices from the action and index buffer"""
        action = self.ctx.GetAction(event_id)
        if action is None:
            return

        layout["num_indices"] = action.numIndices

        indexed = ib is not None and ib.resourceId != rd.ResourceId.Null() and ib.byteStride != 0
        if not indexed:
            # For a non-indexed draw, numIndices is really the vertex count.
            layout["num_vertices"] = action.numIndices
            return

        # Indexed draw: derive a vertex range from the highest index referenced.
        try:
            layout["num_vertices"] = self._count_vertices(controller, action, ib)
        except Exception:
            layout["num_vertices"] = None

    def _count_vertices(self, controller, action, ib):
        """Upper bound on the vertex index referenced by an indexed draw"""
        stride = ib.byteStride
        struct_type = _INDEX_STRUCT_TYPES.get(stride)
        num_indices = action.numIndices

        if struct_type is None or num_indices <= 0:
            return None

        length = num_indices * stride
        if length > _MAX_INDEX_SCAN_BYTES:
            return None

        start = ib.byteOffset + action.indexOffset * stride
        data = controller.GetBufferData(ib.resourceId, start, length)

        indices = struct.unpack_from("=%d%s" % (num_indices, struct_type), data)
        if not indices:
            return None

        # Every fetched index is biased by baseVertex before the vertex lookup.
        count = max(indices) + action.baseVertex + 1
        if count <= 0:
            return None
        return count
