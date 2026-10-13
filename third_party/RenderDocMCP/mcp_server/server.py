"""
RenderDoc MCP Server
FastMCP 2.0 server providing access to RenderDoc capture data.
"""

from typing import Literal

from fastmcp import FastMCP

from . import mesh_export
from .bridge.client import RenderDocBridge, RenderDocBridgeError
from .config import settings

# Initialize FastMCP server
mcp = FastMCP(
    name="RenderDoc MCP Server",
)

# RenderDoc bridge client
bridge = RenderDocBridge(host=settings.renderdoc_host, port=settings.renderdoc_port)


@mcp.tool
def get_capture_status() -> dict:
    """
    Check if a capture is currently loaded in RenderDoc.
    Returns the capture status and API type if loaded.
    """
    return bridge.call("get_capture_status")


@mcp.tool
def get_draw_calls(
    include_children: bool = True,
    marker_filter: str | None = None,
    exclude_markers: list[str] | None = None,
    event_id_min: int | None = None,
    event_id_max: int | None = None,
    only_actions: bool = False,
    flags_filter: list[str] | None = None,
) -> dict:
    """
    Get the list of all draw calls and actions in the current capture.

    Args:
        include_children: Include child actions in the hierarchy (default: True)
        marker_filter: Only include actions under markers containing this string (partial match)
        exclude_markers: Exclude actions under markers containing these strings (list of partial matches)
        event_id_min: Only include actions with event_id >= this value
        event_id_max: Only include actions with event_id <= this value
        only_actions: If True, exclude marker actions (PushMarker/PopMarker/SetMarker)
        flags_filter: Only include actions with these flags (list of flag names, e.g. ["Drawcall", "Dispatch"])

    Returns a hierarchical tree of actions including markers, draw calls,
    dispatches, and other GPU events.
    """
    params: dict[str, object] = {"include_children": include_children}
    if marker_filter is not None:
        params["marker_filter"] = marker_filter
    if exclude_markers is not None:
        params["exclude_markers"] = exclude_markers
    if event_id_min is not None:
        params["event_id_min"] = event_id_min
    if event_id_max is not None:
        params["event_id_max"] = event_id_max
    if only_actions:
        params["only_actions"] = only_actions
    if flags_filter is not None:
        params["flags_filter"] = flags_filter
    return bridge.call("get_draw_calls", params)


@mcp.tool
def get_frame_summary() -> dict:
    """
    Get a summary of the current capture frame.

    Returns statistics about the frame including:
    - API type (D3D11, D3D12, Vulkan, etc.)
    - Total action count
    - Statistics: draw calls, dispatches, clears, copies, presents, markers
    - Top-level markers with event IDs and child counts
    - Resource counts: textures, buffers
    """
    return bridge.call("get_frame_summary")


@mcp.tool
def find_draws_by_shader(
    shader_name: str,
    stage: Literal["vertex", "hull", "domain", "geometry", "pixel", "compute"] | None = None,
) -> dict:
    """
    Find all draw calls using a shader with the given name (partial match).

    Args:
        shader_name: Partial name to search for in shader names or entry points
        stage: Optional shader stage to search (if not specified, searches all stages)

    Returns a list of matching draw calls with event IDs and match reasons.
    """
    params: dict[str, object] = {"shader_name": shader_name}
    if stage is not None:
        params["stage"] = stage
    return bridge.call("find_draws_by_shader", params)


@mcp.tool
def find_draws_by_texture(texture_name: str) -> dict:
    """
    Find all draw calls using a texture with the given name (partial match).

    Args:
        texture_name: Partial name to search for in texture resource names

    Returns a list of matching draw calls with event IDs and match reasons.
    Searches SRVs, UAVs, and render targets.
    """
    return bridge.call("find_draws_by_texture", {"texture_name": texture_name})


@mcp.tool
def find_draws_by_resource(resource_id: str) -> dict:
    """
    Find all draw calls using a specific resource ID (exact match).

    Args:
        resource_id: Resource ID to search for (e.g. "ResourceId::12345" or "12345")

    Returns a list of matching draw calls with event IDs and match reasons.
    Searches shaders, SRVs, UAVs, render targets, and depth targets.
    """
    return bridge.call("find_draws_by_resource", {"resource_id": resource_id})


@mcp.tool
def get_draw_call_details(event_id: int) -> dict:
    """
    Get detailed information about a specific draw call.

    Args:
        event_id: The event ID of the draw call to inspect

    Includes vertex/index counts, resource outputs, and other metadata.
    """
    return bridge.call("get_draw_call_details", {"event_id": event_id})


@mcp.tool
def get_action_timings(
    event_ids: list[int] | None = None,
    marker_filter: str | None = None,
    exclude_markers: list[str] | None = None,
) -> dict:
    """
    Get GPU timing information for actions (draw calls, dispatches, etc.).

    Args:
        event_ids: Optional list of specific event IDs to get timings for.
                   If not specified, returns timings for all actions.
        marker_filter: Only include actions under markers containing this string (partial match).
        exclude_markers: Exclude actions under markers containing these strings.

    Returns timing data including:
    - available: Whether GPU timing counters are supported
    - unit: Time unit (typically "seconds")
    - timings: List of {event_id, name, duration_seconds, duration_ms}
    - total_duration_ms: Sum of all durations
    - count: Number of timing entries

    Note: GPU timing counters may not be available on all hardware/drivers.
    """
    params: dict[str, object] = {}
    if event_ids is not None:
        params["event_ids"] = event_ids
    if marker_filter is not None:
        params["marker_filter"] = marker_filter
    if exclude_markers is not None:
        params["exclude_markers"] = exclude_markers
    return bridge.call("get_action_timings", params)


@mcp.tool
def get_shader_info(
    event_id: int,
    stage: Literal["vertex", "hull", "domain", "geometry", "pixel", "compute"],
) -> dict:
    """
    Get shader information for a specific stage at a given event.

    Args:
        event_id: The event ID to inspect the shader at
        stage: The shader stage (vertex, hull, domain, geometry, pixel, compute)

    Returns shader disassembly, constant buffer values, and resource bindings.
    """
    return bridge.call("get_shader_info", {"event_id": event_id, "stage": stage})


@mcp.tool
def get_buffer_contents(
    resource_id: str,
    offset: int = 0,
    length: int = 0,
) -> dict:
    """
    Read the contents of a buffer resource.

    Args:
        resource_id: The resource ID of the buffer to read
        offset: Byte offset to start reading from (default: 0)
        length: Number of bytes to read, 0 for entire buffer (default: 0)

    Returns buffer data as base64-encoded bytes along with metadata.
    """
    return bridge.call(
        "get_buffer_contents",
        {"resource_id": resource_id, "offset": offset, "length": length},
    )


@mcp.tool
def list_buffers() -> dict:
    """
    List every buffer in the current capture, sorted by length descending.

    Returns a list of {resource_id, name, length}. Useful for locating a
    uniform/constant buffer by name or length before reading it with
    get_buffer_contents.
    """
    return bridge.call("list_buffers")


@mcp.tool
def get_texture_info(resource_id: str) -> dict:
    """
    Get metadata about a texture resource.

    Args:
        resource_id: The resource ID of the texture

    Includes dimensions, format, mip levels, and other properties.
    """
    return bridge.call("get_texture_info", {"resource_id": resource_id})


@mcp.tool
def get_texture_data(
    resource_id: str,
    mip: int = 0,
    slice: int = 0,
    sample: int = 0,
    depth_slice: int | None = None,
) -> dict:
    """
    Read the pixel data of a texture resource.

    Args:
        resource_id: The resource ID of the texture to read
        mip: Mip level to retrieve (default: 0)
        slice: Array slice or cube face index (default: 0)
               For cube maps: 0=X+, 1=X-, 2=Y+, 3=Y-, 4=Z+, 5=Z-
        sample: MSAA sample index (default: 0)
        depth_slice: For 3D textures only, extract a specific depth slice (default: None = full volume)
                     When specified, returns only the 2D slice at that depth index

    Returns texture pixel data as base64-encoded bytes along with metadata
    including dimensions at the requested mip level and format information.
    """
    params = {"resource_id": resource_id, "mip": mip, "slice": slice, "sample": sample}
    if depth_slice is not None:
        params["depth_slice"] = depth_slice
    return bridge.call("get_texture_data", params)


@mcp.tool
def get_pipeline_state(event_id: int) -> dict:
    """
    Get the full graphics pipeline state at a specific event.

    Args:
        event_id: The event ID to get pipeline state at

    Returns detailed pipeline state including:
    - Bound shaders with entry points for each stage
    - Shader resources (SRVs): textures and buffers with dimensions, format, slot, name
    - UAVs (RWTextures/RWBuffers): resource details with dimensions and format
    - Samplers: addressing modes, filter settings, LOD parameters
    - Constant buffers: slot, size, variable count
    - Render targets and depth target
    - Viewports and input assembly state
    """
    return bridge.call("get_pipeline_state", {"event_id": event_id})


@mcp.tool
def get_mesh_layout(event_id: int) -> dict:
    """
    Get the vertex-input (mesh) layout of the draw at a specific event.

    Args:
        event_id: The event ID of the draw call to inspect

    Returns a description of the draw's vertex input including:
    - input_assembly_topology: the primitive topology
    - vertex_buffers: bound vertex buffers (slot, resource id, offset, stride, size)
    - index_buffer: the index buffer binding and whether the draw is indexed
    - attributes: vertex attributes (name, vertex buffer, offset, per-instance,
      rate, used) with the format decomposed into readable fields
    - num_indices / num_vertices: index count from the action and a derived
      vertex count (may be null when it cannot be determined cheaply)
    - suggested_columns: a flat list of per-component tokens (e.g. POSITION.x)
      the user can pick from to choose what to export
    """
    return bridge.call("get_mesh_layout", {"event_id": event_id})


@mcp.tool
def get_mesh_data(event_id: int) -> dict:
    """
    Get the layout plus the raw vertex and index bytes of the draw at an event.

    Args:
        event_id: The event ID of the draw call to inspect

    Returns:
    - layout: the same structure as get_mesh_layout
    - vertex_streams: one entry per distinct (resource_id, byte_offset,
      byte_stride) among the layout's vertex_buffers, each with
      {slot, resource_id, byte_offset, byte_stride, byte_length, data_base64}.
      Streams with byte_stride 0 (generic attributes) are skipped. byte_length
      is byte_stride * num_vertices, never the (possibly sentinel) byte_size.
      Streams that could not be sized/read carry an "error" key instead.
    - index_stream: {resource_id, byte_offset, byte_stride, byte_length,
      data_base64} or None when the draw is not indexed. byte_offset includes
      the draw's index_offset bias.

    Raw bytes are returned so the caller decodes them; no decoding happens in
    the extension.
    """
    return bridge.call("get_mesh_data", {"event_id": event_id})


@mcp.tool
def export_mesh(
    event_id: int | list[int] | None = None,
    columns: str | None = None,
    name: str | None = None,
    out_dir: str | None = None,
    event_ids: list[int] | None = None,
    dedup_draws: bool = True,
) -> dict:
    """
    Decode one or more draw calls' meshes and write them out as CSV (and OBJ).

    Args:
        event_id: The event ID of the (single) draw call to export. A list of
            event IDs is also accepted and means the same as ``event_ids``.
        columns: Optional comma-separated column spec, e.g.
            "pos=_input0.xyz,uv=_input1.xy,normal=normal(_input2)". Each token
            is "name=<decoder>(<attribute>[.<components>])"; the decoder (raw,
            oct_normal, normal) and the .xyzw swizzle are optional. Attribute
            names come from the layout's attributes[].name. When omitted, every
            attribute/component is exported as a raw column named
            "<attribute>.<letter>". The "normal" decoder takes no swizzle and
            accepts either a 32-bit packed octahedral normal or a >=3 component
            32-bit float vector.
        name: Output basename (default "mesh_<event_id>"; "mesh_<first>_<last>"
            for a merged export).
        out_dir: Output directory (default "<repo root>/Output").
        event_ids: Multiple event IDs to decode and merge into one set of
            files. A merged export REQUIRES an explicit ``columns`` spec: the
            default column set is invented per event and cannot be
            concatenated. Each event's indices are remapped by the running
            vertex offset before concatenation.
        dedup_draws: For a merged export, drop a later event whose index and
            vertex-buffer bindings AND decoded vertex/index data match an
            earlier kept event (default True); the drops are reported in
            "duplicates".

    Writes "<name>.vertices.csv" (idx + the spec's columns), "<name>.indices.csv"
    (tri.a,tri.b,tri.c), and "<name>.obj" (v/vt/vn + f, 1-based) when the spec
    names a position column (prefixes pos/position, uv/texcoord, normal/nrm).

    A single event returns {vertices_csv, indices_csv, obj, vertex_count,
    triangle_count, columns, bbox, base_vertex, warnings}. A merged export adds
    {event_ids (kept, in order), duplicates ([{event_id, duplicate_of}]),
    per_event ([{event_id, vertex_count, triangle_count, vertex_offset}])}.
    Only Topology.TriangleList is supported; strips/fans raise. OBJ cannot carry
    skinning -- weights/joints are CSV-only.
    """
    return mesh_export.export_mesh(
        event_id=event_id,
        columns=columns,
        name=name,
        out_dir=out_dir,
        bridge=bridge,
        event_ids=event_ids,
        dedup_draws=dedup_draws,
    )


@mcp.tool
def list_captures(directory: str) -> dict:
    """
    List all RenderDoc capture files (.rdc) in the specified directory.

    Args:
        directory: The directory path to search for capture files

    Returns a list of capture files with their metadata including:
    - filename: The capture file name
    - path: Full path to the file
    - size_bytes: File size in bytes
    - modified_time: Last modified timestamp (ISO format)
    """
    return bridge.call("list_captures", {"directory": directory})


@mcp.tool
def open_capture(capture_path: str) -> dict:
    """
    Open a RenderDoc capture file (.rdc).

    Args:
        capture_path: Full path to the capture file to open

    Returns success status and information about the opened capture.
    Note: This will close any currently open capture.
    """
    return bridge.call("open_capture", {"capture_path": capture_path})


def main():
    """Run the MCP server"""
    mcp.run()


if __name__ == "__main__":
    main()
