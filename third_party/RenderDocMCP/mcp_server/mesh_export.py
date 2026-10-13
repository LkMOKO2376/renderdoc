"""Client-side mesh decoding and export (CSV / OBJ / USD).

The qDHR extension hands back the vertex-input *layout* and the *raw bytes* of
every vertex/index stream (``get_mesh_data``).  Everything below the byte level
lives here, in the MCP server process, on purpose: changing the extension means
restarting the qDHR GUI, changing this file does not.

Standard library only, plus a *lazy* ``pxr`` import for the USD writer -- no
numpy, and `usd-core` is not a declared dependency of this package (see
``pyproject.toml``), so its absence must not break CSV/OBJ export.

Three layers:

* :func:`decode_attribute` -- turn one attribute's raw bytes into a per-vertex
  list of component values (``comp_type``/``comp_byte_width`` driven).
* :func:`decode_oct_normal` -- a derived decoder for packed octahedral normals.
* :func:`export_mesh` -- glue: pull the bytes over the bridge, apply a
  caller-supplied column spec, write ``.vertices.csv`` / ``.indices.csv`` /
  ``.obj`` / ``.usda``.
"""

from __future__ import annotations

import base64
import os
import re
import struct
from dataclasses import dataclass, field

from .bridge.client import RenderDocBridge

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

ROOT_DIR = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)
DEFAULT_OUT_DIR = os.path.join(ROOT_DIR, "Output")

# Letters used for component suffixes, in declaration order.
_COMPONENT_LETTERS = "xyzw"

# struct format character for each (kind, byte width).
_FLOAT_CHARS = {2: "e", 4: "f"}  # 'e' == IEEE 754 half precision
_UNSIGNED_CHARS = {1: "B", 2: "H", 4: "I", 8: "Q"}
_SIGNED_CHARS = {1: "b", 2: "h", 4: "i", 8: "q"}

_UNSIGNED_TYPES = {"UInt", "UNorm", "UNormSRGB", "UScaled"}
_SIGNED_TYPES = {"SInt", "SNorm", "SScaled"}
_INT_TYPES = {"UInt", "SInt"}  # emitted as integers, everything else as floats

_INDEX_CHARS = {1: "B", 2: "H", 4: "I"}

# Substrings that identify a format the simple per-component model cannot
# express.  Anything packed/depth/blocked must be rejected loudly rather than
# decoded into wrong numbers.
_PACKED_MARKERS = (
    "R10G10B10A2",
    "R11G11B10",
    "R9G9B9E5",
    "RGB9E5",
    "BC",
    "_PACK",
    "R5G6B5",
    "B5G6R5",
    "R5G5B5A1",
    "B5G5R5A1",
    "R4G4B4A4",
    "R3G3B2",
    "R8G8_B8G8",
    "G8R8_G8B8",
    "D16",
    "D24",
    "D32",
    "XR10",
)

# ``R32G32B32_FLOAT`` -> groups are (letter, bits) x 1..4.
_COMPONENT_RE = re.compile(
    r"^([RGBA])(\d+)(?:([RGBA])(\d+))?(?:([RGBA])(\d+))?(?:([RGBA])(\d+))?_"
)

# OBJ prefix aliases, matched case-insensitively against the column name.
_POSITION_PREFIXES = ("pos", "position")
_UV_PREFIXES = ("uv", "texcoord", "texcoords", "tex", "tcoord")
_NORMAL_PREFIXES = ("normal", "nrm")

_TOPOLOGY_TRIANGLE_LIST = "Topology.TriangleList"


class MeshExportError(ValueError):
    """Raised for anything the exporter cannot decode unambiguously.

    Subclasses :class:`ValueError` so a malformed column spec and a bad decode
    are both catchable as the standard error type.
    """


# ---------------------------------------------------------------------------
# Stream / format helpers
# ---------------------------------------------------------------------------


def _stream_bytes(stream):
    """base64-decode a stream entry, or raise a clear error."""
    if stream is None:
        raise MeshExportError("no vertex stream is bound for this attribute")
    if stream.get("error"):
        raise MeshExportError("vertex stream unavailable: %s" % stream["error"])
    data = stream.get("data_base64")
    if not data:
        raise MeshExportError("vertex stream carries no data")
    return base64.b64decode(data)


def _comp_type_name(attribute):
    name = attribute.get("comp_type") or ""
    prefix = "CompType."
    if name.startswith(prefix):
        name = name[len(prefix) :]
    return name


def _check_format(attribute):
    """Reject formats the per-component decoder cannot represent faithfully."""
    fmt_name = attribute.get("format_name") or ""
    attr_name = attribute.get("name") or "?"

    for marker in _PACKED_MARKERS:
        if marker in fmt_name:
            raise MeshExportError(
                "attribute %r has packed/special format %s, which the component "
                "decoder cannot express" % (attr_name, fmt_name)
            )

    match = _COMPONENT_RE.match(fmt_name)
    if match is None:
        raise MeshExportError(
            "attribute %r has format %s, which is not a simple per-component "
            "format" % (attr_name, fmt_name)
        )

    widths = [int(match.group(i)) for i in (2, 4, 6, 8) if match.group(i)]
    count = attribute.get("comp_count") or 0
    byte_width = attribute.get("comp_byte_width") or 0
    if len(widths) != count or any(w != 8 * byte_width for w in widths):
        raise MeshExportError(
            "attribute %r has format %s whose %s component(s) of %d bit do not "
            "match comp_count=%d / comp_byte_width=%d"
            % (attr_name, fmt_name, widths, 8 * byte_width, count, byte_width)
        )


def _attribute_plan(attribute):
    """Return ``(struct_char, comp_type, byte_width, comp_count)``.

    Raises :class:`MeshExportError` for formats/types outside the model.
    """
    _check_format(attribute)

    comp_type = _comp_type_name(attribute)
    width = attribute.get("comp_byte_width")
    count = attribute.get("comp_count") or 0
    if count <= 0:
        raise MeshExportError(
            "attribute %r declares no components" % (attribute.get("name") or "?")
        )

    if comp_type == "Float":
        char = _FLOAT_CHARS.get(width)
    elif comp_type in _UNSIGNED_TYPES:
        char = _UNSIGNED_CHARS.get(width)
    elif comp_type in _SIGNED_TYPES:
        char = _SIGNED_CHARS.get(width)
    else:
        raise MeshExportError(
            "attribute %r has unsupported component type %s"
            % (attribute.get("name") or "?", comp_type or "<none>")
        )

    if char is None:
        raise MeshExportError(
            "attribute %r: no decode for comp_type %s at %s bytes/component"
            % (attribute.get("name") or "?", comp_type, width)
        )
    return char, comp_type, width, count


def _srgb_to_linear(value):
    """sRGB electro-optical transfer function (what the shader receives)."""
    if value <= 0.04045:
        return value / 12.92
    return ((value + 0.055) / 1.055) ** 2.4


def _convert(comp_type, width, raw):
    """Convert one raw integer/float component to its shader-visible value."""
    if comp_type in ("Float", "UInt", "SInt"):
        return raw
    if comp_type == "UNorm":
        return raw / float(2 ** (8 * width) - 1)
    if comp_type == "UNormSRGB":
        return _srgb_to_linear(raw / float(2 ** (8 * width) - 1))
    if comp_type == "SNorm":
        return max(-1.0, raw / float(2 ** (8 * width - 1) - 1))
    # UScaled / SScaled: the integer reinterpreted as a float, unscaled.
    return float(raw)


def decode_attribute(attribute, stream, vertex_count):
    """Decode one attribute into ``vertex_count`` rows of component values.

    ``stream`` is the ``get_mesh_data`` ``vertex_streams`` entry whose
    ``slot`` equals ``attribute["vertex_buffer"]``.  Each vertex lives at
    ``i * stream["byte_stride"] + attribute["byte_offset"]``.

    Returns a list of tuples, one per vertex, each of ``comp_count`` values.
    Ints stay ints (UInt/SInt); everything else is a float.
    """
    char, comp_type, width, count = _attribute_plan(attribute)

    if stream is None:
        raise MeshExportError(
            "attribute %r has no readable vertex stream (stride 0 / generic)"
            % (attribute.get("name") or "?")
        )
    raw = _stream_bytes(stream)
    stride = stream.get("byte_stride") or 0
    if stride <= 0:
        raise MeshExportError(
            "attribute %r: stream has no stride" % (attribute.get("name") or "?")
        )

    fmt = "<" + char * count
    size = struct.calcsize(fmt)
    base = attribute.get("byte_offset", 0) or 0
    unpack_from = struct.unpack_from

    rows = []
    for i in range(vertex_count):
        offset = base + i * stride
        if offset + size > len(raw):
            raise MeshExportError(
                "attribute %r: vertex %d reads past the end of its stream "
                "(%d bytes)" % (attribute.get("name") or "?", i, len(raw))
            )
        values = unpack_from(fmt, raw, offset)
        rows.append(tuple(_convert(comp_type, width, v) for v in values))
    return rows


# ---------------------------------------------------------------------------
# Derived decoders
# ---------------------------------------------------------------------------


def decode_oct_normal(value):
    """Decode a 32-bit packed octahedral normal into an ``(x, y, z)`` triple.

    The low 20 bits hold two 10-bit *signed* fields (``v >= 512 -> v - 1024``)
    scaled by 0.0020.  ``z`` is reconstructed as ``1 - |x| - |y|``; when it is
    negative the vector is folded onto the lower hemisphere.  The result is
    normalised, so its length is 1.0.
    """
    value &= 0xFFFFFFFF
    low = value & 0xFFFFF
    xv = low & 0x3FF
    yv = (low >> 10) & 0x3FF
    x = (xv - 1024 if xv >= 512 else xv) * 0.0020
    y = (yv - 1024 if yv >= 512 else yv) * 0.0020
    z = 1.0 - abs(x) - abs(y)
    if z < 0.0:
        # Fold while the original x/y are still in hand.
        ox, oy = x, y
        x = (1.0 - abs(oy)) * (1.0 if ox >= 0.0 else -1.0)
        y = (1.0 - abs(ox)) * (1.0 if oy >= 0.0 else -1.0)
    length = (x * x + y * y + z * z) ** 0.5
    if length == 0.0:
        return (0.0, 0.0, 1.0)
    return (x / length, y / length, z / length)


def _decode_oct_column(column, stream, vertex_count):
    """The packed-octahedral decoder body, shared by ``oct_normal``/``normal``."""
    width = column.attribute.get("comp_byte_width") or 0
    if width != 4:
        raise MeshExportError(
            "column %r: oct_normal needs a 32-bit attribute, %r is %s byte(s)"
            % (column.name, column.attribute_name, width)
        )
    raw = _stream_bytes(stream)
    stride = stream["byte_stride"]
    base = column.attribute.get("byte_offset", 0) or 0
    unpack_from = struct.unpack_from
    values = []
    for i in range(vertex_count):
        offset = base + i * stride
        if offset + 4 > len(raw):
            raise MeshExportError(
                "column %r: vertex %d reads past the end of its stream"
                % (column.name, i)
            )
        packed = unpack_from("<I", raw, offset)[0]
        values.append(decode_oct_normal(packed))
    return values, ["x", "y", "z"], False


def _decode_normal_column(column, stream, vertex_count):
    """Decode a normal attribute in either of its two encodings.

    A single 32-bit component is a packed octahedral normal; a 3+ component
    32-bit float vector is plain ``(x, y, z)``.  Anything else is rejected
    rather than guessed.
    """
    attribute = column.attribute
    comp_type = _comp_type_name(attribute)
    count = attribute.get("comp_count") or 0
    width = attribute.get("comp_byte_width") or 0

    if count == 1 and width == 4:
        return _decode_oct_column(column, stream, vertex_count)

    if count >= 3 and comp_type == "Float" and width == 4:
        rows = decode_attribute(attribute, stream, vertex_count)
        return [tuple(row[:3]) for row in rows], ["x", "y", "z"], False

    raise MeshExportError(
        "column %r: attribute %r has format %s, which 'normal' cannot decode "
        "(accepted: one 32-bit packed octahedral component, or a >=3 component "
        "32-bit float vector)"
        % (
            column.name,
            column.attribute_name,
            attribute.get("format_name") or "<unknown>",
        )
    )


# Decoder registry. ``raw`` is the default; ``oct_normal`` and ``normal``
# consume the whole attribute and so take no swizzle.
DECODERS = {
    "raw": {"components": None, "swizzle": True},
    "oct_normal": {"components": ("x", "y", "z"), "swizzle": False},
    "normal": {"components": ("x", "y", "z"), "swizzle": False},
}


# ---------------------------------------------------------------------------
# Column spec
# ---------------------------------------------------------------------------


@dataclass
class Column:
    """One decoded column group from the caller's spec."""

    name: str
    decoder: str
    attribute_name: str
    attribute: dict
    swizzle: list | None = None
    labels: list = field(default_factory=list)


_BARE_RE = re.compile(r"^([A-Za-z_]\w*)\s*(?:\.\s*([xyzw]+))?$")
_CALL_RE = re.compile(r"^([A-Za-z_]\w*)\s*\(\s*([A-Za-z_]\w*)\s*(?:\.\s*([xyzw]+))?\s*\)$")


def _attribute_lookup(attributes):
    """Map attribute name -> attribute dict, first occurrence wins."""
    lookup = {}
    for index, attr in enumerate(attributes):
        name = attr.get("name") or ("attr%d" % index)
        lookup.setdefault(name, attr)
    return lookup


def parse_columns(spec, attributes):
    """Parse a column spec into :class:`Column` objects.

    Grammar -- comma-separated, ordered::

        name=<decoder>(<attribute>[.<components>])

    ``<decoder>`` is optional (default ``raw``); the parentheses and swizzle
    are optional too, so ``pos=_input0.xyz`` and ``n=oct_normal(_input2)`` are
    both accepted.  A malformed token raises :class:`MeshExportError` naming
    the offending piece.
    """
    lookup = _attribute_lookup(attributes)
    columns = []
    seen_names = set()

    for raw_token in spec.split(","):
        token = raw_token.strip()
        if not token:
            raise MeshExportError("empty column token in spec: %r" % spec)

        if "=" not in token:
            raise MeshExportError(
                "column token %r is missing the 'name=' assignment" % token
            )
        name, rhs = token.split("=", 1)
        name = name.strip()
        rhs = rhs.strip()
        if not name:
            raise MeshExportError("column token %r has an empty name" % token)
        if name == "idx":
            raise MeshExportError("column name 'idx' is reserved for the index column")

        if "(" in rhs or ")" in rhs:
            match = _CALL_RE.match(rhs)
            if match is None:
                raise MeshExportError(
                    "column token %r is not a valid decoder call "
                    "(expected decoder(attribute[.components]))" % token
                )
            decoder, attr_name, swizzle = match.group(1), match.group(2), match.group(3)
        else:
            match = _BARE_RE.match(rhs)
            if match is None:
                raise MeshExportError(
                    "column token %r is not a valid attribute reference "
                    "(expected attribute[.components])" % token
                )
            decoder, attr_name, swizzle = "raw", match.group(1), match.group(2)

        if decoder not in DECODERS:
            raise MeshExportError(
                "column token %r uses unknown decoder %r (known: %s)"
                % (token, decoder, ", ".join(sorted(DECODERS)))
            )
        if attr_name not in lookup:
            raise MeshExportError(
                "column token %r references unknown attribute %r "
                "(layout has: %s)"
                % (
                    token,
                    attr_name,
                    ", ".join(sorted(lookup)) or "<none>",
                )
            )

        attribute = lookup[attr_name]
        meta = DECODERS[decoder]

        if meta["components"] is not None:
            if swizzle:
                raise MeshExportError(
                    "column token %r: decoder %r takes no component swizzle"
                    % (token, decoder)
                )
            labels = list(meta["components"])
            indices = None
        else:
            count = attribute.get("comp_count") or 0
            if count <= 0:
                raise MeshExportError(
                    "column token %r: attribute %r declares no components"
                    % (token, attr_name)
                )
            if swizzle:
                indices = []
                for letter in swizzle:
                    position = _COMPONENT_LETTERS.find(letter)
                    if position < 0 or position >= count:
                        raise MeshExportError(
                            "column token %r: component '.%s' is out of range for "
                            "attribute %r (has %d component(s))"
                            % (token, letter, attr_name, count)
                        )
                    indices.append(position)
                labels = list(swizzle)
            else:
                indices = list(range(count))
                labels = list(_COMPONENT_LETTERS[:count])

        if name in seen_names:
            raise MeshExportError("column name %r is used more than once" % name)
        seen_names.add(name)

        columns.append(
            Column(
                name=name,
                decoder=decoder,
                attribute_name=attr_name,
                attribute=attribute,
                swizzle=indices,
                labels=labels,
            )
        )

    if not columns:
        raise MeshExportError("column spec produced no columns")
    return columns


def default_columns(attributes, stream_for):
    """Every attribute, every component, as raw columns.

    Attributes with no readable stream (stride 0 / generic) are skipped and
    returned separately so the caller can report them instead of silently
    emitting wrong numbers.
    """
    columns = []
    skipped = []
    for index, attr in enumerate(attributes):
        name = attr.get("name") or ("attr%d" % index)
        if stream_for(attr) is None:
            skipped.append(
                {
                    "attribute": name,
                    "reason": "no readable vertex stream (stride 0 / generic)",
                }
            )
            continue
        count = attr.get("comp_count") or 0
        if count <= 0:
            skipped.append({"attribute": name, "reason": "no components declared"})
            continue
        columns.append(
            Column(
                name=name,
                decoder="raw",
                attribute_name=name,
                attribute=attr,
                swizzle=list(range(count)),
                labels=list(_COMPONENT_LETTERS[:count]),
            )
        )
    return columns, skipped


# ---------------------------------------------------------------------------
# Decoding a column
# ---------------------------------------------------------------------------


def _decode_column(column, stream_for, vertex_count):
    """Return ``(values, labels, is_int)`` for one column."""
    attribute = column.attribute
    stream = stream_for(attribute)
    if stream is None:
        raise MeshExportError(
            "column %r: attribute %r has no readable vertex stream"
            % (column.name, column.attribute_name)
        )

    if column.decoder == "oct_normal":
        return _decode_oct_column(column, stream, vertex_count)

    if column.decoder == "normal":
        return _decode_normal_column(column, stream, vertex_count)

    rows = decode_attribute(attribute, stream, vertex_count)
    indices = column.swizzle if column.swizzle is not None else list(
        range(attribute.get("comp_count") or 0)
    )
    values = [tuple(row[j] for j in indices) for row in rows]
    is_int = _comp_type_name(attribute) in _INT_TYPES
    return values, list(column.labels), is_int


# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------


def _fmt(value, is_int):
    if is_int:
        return "%d" % int(value)
    return "%.6f" % value


def _find_by_prefix(decoded, prefixes):
    """First decoded column whose (lower-cased) name matches a prefix."""
    for entry in decoded:
        if entry["column"].name.lower() in prefixes:
            return entry
    return None


# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------


def _flat_names(decoded):
    """Flat ``<column>.<label>`` header tokens for a decoded column set."""
    names = []
    for entry in decoded:
        names.extend(
            "%s.%s" % (entry["column"].name, label) for label in entry["labels"]
        )
    return names


def _write_vertices_csv(out_dir, name, decoded, vertex_count):
    """Write ``<name>.vertices.csv``; returns ``(path, flat_names)``."""
    flat_names = _flat_names(decoded)
    lines = ["idx," + ",".join(flat_names)]
    for i in range(vertex_count):
        cells = [str(i)]
        for entry in decoded:
            for value in entry["values"][i]:
                cells.append(_fmt(value, entry["is_int"]))
        lines.append(",".join(cells))
    path = os.path.join(out_dir, "%s.vertices.csv" % name)
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write("\n".join(lines) + "\n")
    return path, flat_names


def _write_indices_csv(out_dir, name, indices):
    """Write ``<name>.indices.csv``; returns ``(path, triangle_count)``."""
    triangle_count = len(indices) // 3
    lines = ["tri.a,tri.b,tri.c"]
    for t in range(triangle_count):
        a, b, c = indices[3 * t : 3 * t + 3]
        lines.append("%d,%d,%d" % (a, b, c))
    path = os.path.join(out_dir, "%s.indices.csv" % name)
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write("\n".join(lines) + "\n")
    return path, triangle_count


def _obj_columns(decoded, warnings):
    """Pick and validate the position/uv/normal columns an OBJ will use.

    Position/uv/normal columns are picked by name prefix.  Returns
    ``(pos_entry, uv_entry, nrm_entry)``; ``pos_entry`` is ``None`` (with a
    warning appended) when no position column is named, which is the condition
    under which the OBJ is skipped entirely.
    """
    pos_entry = _find_by_prefix(decoded, _POSITION_PREFIXES)
    uv_entry = _find_by_prefix(decoded, _UV_PREFIXES)
    nrm_entry = _find_by_prefix(decoded, _NORMAL_PREFIXES)

    if pos_entry is None:
        warnings.append(
            "no position column (name one of %s) -- OBJ skipped"
            % "/".join(_POSITION_PREFIXES)
        )
        return None, None, None
    if len(pos_entry["labels"]) < 3:
        raise MeshExportError(
            "position column %r needs 3 components, has %d"
            % (pos_entry["column"].name, len(pos_entry["labels"]))
        )
    if uv_entry is not None and len(uv_entry["labels"]) < 2:
        raise MeshExportError(
            "uv column %r needs 2 components, has %d"
            % (uv_entry["column"].name, len(uv_entry["labels"]))
        )
    if nrm_entry is not None and len(nrm_entry["labels"]) < 3:
        raise MeshExportError(
            "normal column %r needs 3 components, has %d"
            % (nrm_entry["column"].name, len(nrm_entry["labels"]))
        )
    return pos_entry, uv_entry, nrm_entry


def _column_entry(decoded, column_name):
    """The decoded entry named ``column_name`` (``None`` when absent)."""
    for entry in decoded:
        if entry["column"].name == column_name:
            return entry
    return None


def _bbox(pos_values):
    """Axis-aligned bounds of a sequence of ``(x, y, z, ...)`` rows."""
    return {
        "x": [min(row[0] for row in pos_values), max(row[0] for row in pos_values)],
        "y": [min(row[1] for row in pos_values), max(row[1] for row in pos_values)],
        "z": [min(row[2] for row in pos_values), max(row[2] for row in pos_values)],
    }


def _append_obj_section(
    lines, obj_name, pos_entry, uv_entry, nrm_entry, indices, triangle_count,
    index_offset=0,
):
    """Append one ``o`` section and its ``v``/``vt``/``vn``/``f`` to ``lines``.

    ``indices`` are this object's own 0-based, base-vertex-biased values;
    ``index_offset`` is the number of vertices already written by earlier
    objects in the file, so the emitted 1-based face indices are file-global
    and keep counting across ``o`` sections.
    """
    lines.append("o %s" % obj_name)
    for row in pos_entry["values"]:
        lines.append("v %.6f %.6f %.6f" % (row[0], row[1], row[2]))
    has_uvs = uv_entry is not None
    if has_uvs:
        for row in uv_entry["values"]:
            lines.append("vt %.6f %.6f" % (row[0], row[1]))
    has_normals = nrm_entry is not None
    if has_normals:
        for row in nrm_entry["values"]:
            lines.append("vn %.6f %.6f %.6f" % (row[0], row[1], row[2]))

    for t in range(triangle_count):
        face = []
        for k in range(3):
            idx = indices[3 * t + k] + index_offset + 1
            if has_uvs and has_normals:
                face.append("%d/%d/%d" % (idx, idx, idx))
            elif has_normals:
                face.append("%d//%d" % (idx, idx))
            else:
                face.append("%d" % idx)
        lines.append("f " + " ".join(face))


def _write_obj_section_file(out_dir, name, lines):
    """Write ``lines`` to ``<name>.obj``; returns the path."""
    path = os.path.join(out_dir, "%s.obj" % name)
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write("\n".join(lines) + "\n")
    return path


def _write_obj(out_dir, name, decoded, indices, triangle_count, warnings):
    """Write a single-event ``<name>.obj``; returns ``(path_or_None, bbox)``.

    The mesh is emitted as one ``o <name>`` section.  Without a position column
    the OBJ is skipped and a warning is appended instead.
    """
    pos_entry, uv_entry, nrm_entry = _obj_columns(decoded, warnings)
    if pos_entry is None:
        return None, None

    bbox = _bbox(pos_entry["values"])

    obj_lines = []
    _append_obj_section(
        obj_lines, name, pos_entry, uv_entry, nrm_entry, indices, triangle_count
    )
    path = _write_obj_section_file(out_dir, name, obj_lines)
    return path, bbox


def _write_obj_merged(out_dir, name, kept, warnings):
    """Write the merged ``<name>.obj``; returns ``(path_or_None, bbox)``.

    Every kept event becomes its own ``o ev<event_id>`` section with its own
    ``v``/``vt``/``vn`` blocks -- vertices are neither shared nor de-duplicated
    across events.  Face indices are file-global and 1-based, continuing across
    sections by the running vertex total (each object's base index minus one).
    """
    pos_entry, uv_entry, nrm_entry = _obj_columns(kept[0]["decoded"], warnings)
    if pos_entry is None:
        return None, None

    pos_name = pos_entry["column"].name
    uv_name = uv_entry["column"].name if uv_entry is not None else None
    nrm_name = nrm_entry["column"].name if nrm_entry is not None else None

    # The bbox spans every kept event's positions, not just the first.
    all_positions = []
    for record in kept:
        all_positions.extend(_column_entry(record["decoded"], pos_name)["values"])
    bbox = _bbox(all_positions)

    obj_lines = []
    vertex_offset = 0
    for record in kept:
        decoded = record["decoded"]
        _append_obj_section(
            obj_lines,
            "ev%d" % record["event_id"],
            _column_entry(decoded, pos_name),
            _column_entry(decoded, uv_name) if uv_name else None,
            _column_entry(decoded, nrm_name) if nrm_name else None,
            record["indices"],
            len(record["indices"]) // 3,
            index_offset=vertex_offset,
        )
        vertex_offset += record["vertex_count"]

    path = _write_obj_section_file(out_dir, name, obj_lines)
    return path, bbox


# ---------------------------------------------------------------------------
# Static-mesh USD (.usda) export
# ---------------------------------------------------------------------------


# A USD prim name is a C-like identifier: [A-Za-z_][A-Za-z0-9_]*.
_PRIM_NAME_RE = re.compile(r"[^A-Za-z0-9_]")


def _usd_modules():
    """Import the USD bindings on demand.

    ``usd-core`` is not a declared dependency of this package, so a missing
    ``pxr`` must leave CSV/OBJ export working; callers turn the ImportError
    into a warning and skip only the ``.usda``.
    """
    from pxr import Gf, Sdf, Usd, UsdGeom, Vt

    return Usd, UsdGeom, Sdf, Gf, Vt


def _sanitize_prim_name(name):
    """Coerce ``name`` into a legal USD prim name.

    Dots are not allowed in a prim name, so a basename like ``ev499.usd_check``
    has to be rewritten before it can go on the stage.
    """
    cleaned = _PRIM_NAME_RE.sub("_", name or "")
    if not cleaned:
        return "mesh"
    if cleaned[0].isdigit():
        return "_" + cleaned
    return cleaned


def _set_usd_primvar_role(primvar, role, warnings):
    """Best-effort primvar ``role``; warns when the build cannot express it.

    Upstream USD exposes ``UsdGeom.Primvar.SetRole``.  The ``usd-core`` build
    in this repo's venv does not bind it, and ``role`` is not a registered
    metadata key there either -- ``Usd.Attribute.SetMetadata("role", ...)``
    raises "Unregistered metadata key" and ``Sdf``'s per-spec ``SetInfo``
    rejects it as an "Invalid info key".  ``GetRoleName`` still reports roles,
    but only the ones the schema infers from an attribute's name (``normals``
    -> Normal, ``primvars:displayColor`` -> Color), which is why the uv primvar
    gets a warning instead of a silent no-op.
    """
    attribute = primvar.GetAttr()

    setter = getattr(primvar, "SetRole", None)
    if setter is not None:
        try:
            setter(role)
        except Exception:  # pragma: no cover - build dependent
            pass
        if attribute.GetRoleName() == role:
            return True

    try:
        attribute.SetMetadata("role", role)
    except Exception:
        pass
    if attribute.GetRoleName() == role:
        return True

    warnings.append(
        "could not set role %r on %s: this usd-core build exposes no primvar "
        "role API (UsdGeom.Primvar.SetRole is unbound and 'role' is not a "
        "registered metadata key); the primvar itself was written"
        % (role, attribute.GetPath())
    )
    return False


def _fill_usd_mesh(
    modules, mesh, pos_entry, uv_entry, nrm_entry, indices, triangle_count,
    event_id, warnings,
):
    """Fill one ``UsdGeom.Mesh`` with a static triangle mesh.

    Returns the mesh's own bbox (as :func:`_bbox` builds it) for its ``extent``.
    ``_append_obj_section`` writes faces as ``idx/idx/idx``, i.e. position, uv
    and normal all share one index, so the primvars are non-indexed
    ``vertex``-interpolated arrays: no ``primvar`` indices are needed.
    """
    Usd, UsdGeom, Sdf, Gf, Vt = modules

    positions = pos_entry["values"]
    bbox = _bbox(positions)

    mesh.CreatePointsAttr(
        Vt.Vec3fArray([Gf.Vec3f(row[0], row[1], row[2]) for row in positions])
    )
    mesh.CreateFaceVertexIndicesAttr(Vt.IntArray([int(i) for i in indices]))
    mesh.CreateFaceVertexCountsAttr(Vt.IntArray([3] * triangle_count))
    mesh.CreateSubdivisionSchemeAttr(UsdGeom.Tokens.none)
    mesh.CreateDoubleSidedAttr(True)
    mesh.CreateExtentAttr(
        Vt.Vec3fArray(
            [
                Gf.Vec3f(bbox["x"][0], bbox["y"][0], bbox["z"][0]),
                Gf.Vec3f(bbox["x"][1], bbox["y"][1], bbox["z"][1]),
            ]
        )
    )

    if nrm_entry is not None:
        normals = mesh.CreateNormalsAttr(
            Vt.Vec3fArray(
                [Gf.Vec3f(row[0], row[1], row[2]) for row in nrm_entry["values"]]
            )
        )
        # The schema's default for ``normals`` is ``constant``.
        UsdGeom.Primvar(normals).SetInterpolation(UsdGeom.Tokens.vertex)

    if uv_entry is not None:
        uv_primvar = UsdGeom.PrimvarsAPI(mesh).CreatePrimvar(
            "st", Sdf.ValueTypeNames.Float2Array, UsdGeom.Tokens.vertex
        )
        uv_primvar.Set(
            Vt.Vec2fArray([Gf.Vec2f(row[0], row[1]) for row in uv_entry["values"]])
        )
        _set_usd_primvar_role(
            uv_primvar, Sdf.ValueRoleNames.TextureCoordinate, warnings
        )

    if event_id is not None:
        mesh.GetPrim().SetCustomDataByKey("dhr:eventId", int(event_id))

    return bbox


def _new_usd_stage(usd, usd_geom, prim_name):
    """An in-memory stage with the root Xform; returns ``(stage, root_path)``.

    In-memory plus ``GetRootLayer().Export`` rather than ``Usd.Stage.CreateNew``
    because the latter refuses a path it has already created in this process --
    and the MCP server is one long-lived process.
    """
    stage = usd.Stage.CreateInMemory()
    usd_geom.SetStageUpAxis(stage, usd_geom.Tokens.y)
    usd_geom.SetStageMetersPerUnit(stage, 1.0)
    root = usd_geom.Xform.Define(stage, "/%s" % prim_name)
    stage.SetDefaultPrim(root.GetPrim())
    return stage, root


def _write_usda(
    out_dir, name, decoded, indices, triangle_count, warnings, event_id=None
):
    """Write a single-event ``<name>.usda``; returns ``(path_or_None, bbox)``.

    One ``UsdGeom.Mesh`` named after ``name`` under a root ``UsdGeom.Xform``
    named from the sanitised ``name``.  Without a position column the file is
    skipped and a warning is appended instead, exactly like :func:`_write_obj`.

    ``event_id`` (optional) is recorded as ``customData`` on the mesh prim; the
    task-mandated signature carries no event id, so the caller passes it.
    """
    pos_entry, uv_entry, nrm_entry = _obj_columns(decoded, warnings)
    if pos_entry is None:
        return None, None

    try:
        modules = _usd_modules()
    except ImportError as exc:
        warnings.append("usd-core (pxr) is unavailable: %s -- .usda skipped" % exc)
        return None, None
    Usd, UsdGeom, Sdf, Gf, Vt = modules

    prim_name = _sanitize_prim_name(name)
    stage, root = _new_usd_stage(Usd, UsdGeom, prim_name)
    mesh = UsdGeom.Mesh.Define(stage, "/%s/%s" % (prim_name, prim_name))
    bbox = _fill_usd_mesh(
        modules, mesh, pos_entry, uv_entry, nrm_entry, indices, triangle_count,
        event_id, warnings,
    )

    path = os.path.join(out_dir, "%s.usda" % name)
    stage.GetRootLayer().Export(path)
    return path, bbox


def _write_usda_merged(out_dir, name, kept, warnings):
    """Write the merged ``<name>.usda``; returns ``(path_or_None, bbox)``.

    Every kept event becomes its own ``UsdGeom.Mesh`` prim named
    ``ev<event_id>`` -- its own ``points``/``faceVertexIndices``, vertices
    neither shared nor de-duplicated across events -- all under one root
    ``UsdGeom.Xform``.  The USD twin of :func:`_write_obj_merged`.
    """
    pos_entry, uv_entry, nrm_entry = _obj_columns(kept[0]["decoded"], warnings)
    if pos_entry is None:
        return None, None

    try:
        modules = _usd_modules()
    except ImportError as exc:
        warnings.append("usd-core (pxr) is unavailable: %s -- .usda skipped" % exc)
        return None, None
    Usd, UsdGeom, Sdf, Gf, Vt = modules

    pos_name = pos_entry["column"].name
    uv_name = uv_entry["column"].name if uv_entry is not None else None
    nrm_name = nrm_entry["column"].name if nrm_entry is not None else None

    # The bbox spans every kept event's positions, not just the first.
    all_positions = []
    for record in kept:
        all_positions.extend(_column_entry(record["decoded"], pos_name)["values"])
    bbox = _bbox(all_positions)

    prim_name = _sanitize_prim_name(name)
    stage, root = _new_usd_stage(Usd, UsdGeom, prim_name)

    for record in kept:
        decoded = record["decoded"]
        piece = _sanitize_prim_name("ev%d" % record["event_id"])
        mesh = UsdGeom.Mesh.Define(stage, "/%s/%s" % (prim_name, piece))
        _fill_usd_mesh(
            modules,
            mesh,
            _column_entry(decoded, pos_name),
            _column_entry(decoded, uv_name) if uv_name else None,
            _column_entry(decoded, nrm_name) if nrm_name else None,
            record["indices"],
            len(record["indices"]) // 3,
            record["event_id"],
            warnings,
        )

    path = os.path.join(out_dir, "%s.usda" % name)
    stage.GetRootLayer().Export(path)
    return path, bbox


def _draw_signature(index_stream, vertex_buffers):
    """Cheap identity for a draw: its index binding plus every non-zero-stride
    vertex-buffer binding.  Two events sharing it *may* be the same geometry;
    the decoded data is the real check."""
    index_part = (
        index_stream.get("resource_id"),
        index_stream.get("byte_offset"),
        index_stream.get("byte_stride"),
    )
    vertex_part = tuple(
        sorted(
            (vb.get("resource_id"), vb.get("byte_offset"), vb.get("byte_stride"))
            for vb in vertex_buffers
            if (vb.get("byte_stride") or 0) != 0
        )
    )
    return (index_part, vertex_part)


def _same_decoded(a, b):
    """True when two events decode to identical vertex rows and index lists."""
    if a["indices"] != b["indices"]:
        return False
    if len(a["decoded"]) != len(b["decoded"]):
        return False
    for entry_a, entry_b in zip(a["decoded"], b["decoded"]):
        if entry_a["values"] != entry_b["values"]:
            return False
    return True


def _decode_event(bridge, event_id, columns, warnings, name_errors=False):
    """Fetch and decode a single event's mesh.

    ``columns`` is the raw spec, or ``None`` for the default per-event column
    set (only meaningful for a single event).  ``warnings`` is the shared list
    the caller reports.  ``name_errors`` prefixes decode failures with the
    event id, which matters when several events are merged.

    Returns the decoded columns, the base-vertex-biased indices and the draw
    signature used for duplicate detection.
    """
    data = bridge.call("get_mesh_data", {"event_id": int(event_id)})
    if not data or not data.get("layout"):
        raise MeshExportError("bridge returned no mesh data for event %s" % event_id)

    layout = data["layout"]
    topology = layout.get("input_assembly_topology") or ""
    if topology != _TOPOLOGY_TRIANGLE_LIST:
        raise MeshExportError(
            "mesh export only supports %s; event %s is %s (indexed OBJ faces "
            "would be wrong for strip/fan)"
            % (_TOPOLOGY_TRIANGLE_LIST, event_id, topology or "<unknown>")
        )

    vertex_count = layout.get("num_vertices")
    if not vertex_count or vertex_count <= 0:
        raise MeshExportError(
            "event %s: could not determine a vertex count" % event_id
        )

    streams_by_slot = {s["slot"]: s for s in data.get("vertex_streams", [])}
    vertex_buffers = layout.get("vertex_buffers", [])

    def stream_for(attribute):
        slot = attribute.get("vertex_buffer")
        if slot in streams_by_slot:
            return streams_by_slot[slot]
        # The extension de-duplicates streams sharing (resource, offset, stride),
        # so a slot can be missing; fall back to the binding-level match.
        for vb in vertex_buffers:
            if vb.get("slot") != slot:
                continue
            for stream in data.get("vertex_streams", []):
                if (
                    stream["resource_id"],
                    stream["byte_offset"],
                    stream["byte_stride"],
                ) == (vb["resource_id"], vb["byte_offset"], vb["byte_stride"]):
                    return stream
        return None

    if columns is None:
        specs, skipped = default_columns(layout.get("attributes", []), stream_for)
        for item in skipped:
            warnings.append(
                "skipped attribute %s: %s" % (item["attribute"], item["reason"])
            )
    else:
        try:
            specs = parse_columns(columns, layout.get("attributes", []))
        except MeshExportError as exc:
            if name_errors:
                raise MeshExportError("event %s: %s" % (event_id, exc))
            raise

    decoded = []
    for spec in specs:
        values, labels, is_int = _decode_column(spec, stream_for, vertex_count)
        decoded.append(
            {
                "column": spec,
                "values": values,
                "labels": labels,
                "is_int": is_int,
            }
        )

    index_stream = data.get("index_stream")
    if not index_stream or not index_stream.get("data_base64"):
        reason = (index_stream or {}).get("error", "draw is not indexed")
        raise MeshExportError(
            "event %s: cannot read the index buffer: %s" % (event_id, reason)
        )

    stride = index_stream.get("byte_stride")
    char = _INDEX_CHARS.get(stride)
    if char is None:
        raise MeshExportError(
            "event %s: unsupported index element size %s bytes" % (event_id, stride)
        )
    raw_indices = base64.b64decode(index_stream["data_base64"])
    num_indices = layout.get("num_indices") or (len(raw_indices) // stride)
    available = len(raw_indices) // stride
    if num_indices > available:
        num_indices = available
    indices = list(
        struct.unpack_from("<%d%s" % (num_indices, char), raw_indices, 0)
    )

    # Index values are biased by the draw's base vertex before the lookup.  The
    # mesh payload does not carry it, so ask the bridge; a failure here is not
    # fatal (base vertex is 0 for the overwhelming majority of draws).
    base_vertex = 0
    try:
        details = bridge.call("get_draw_call_details", {"event_id": int(event_id)})
        base_vertex = int((details or {}).get("base_vertex") or 0)
    except Exception as exc:  # pragma: no cover - best effort only
        warnings.append("could not read base_vertex: %s" % exc)
    if base_vertex:
        indices = [i + base_vertex for i in indices]

    if len(indices) % 3:
        warnings.append(
            "%d index value(s) left over (not a whole number of triangles)"
            % (len(indices) % 3)
        )

    return {
        "event_id": int(event_id),
        "layout": layout,
        "vertex_count": vertex_count,
        "decoded": decoded,
        "indices": indices,
        "base_vertex": base_vertex,
        "index_stream": index_stream,
        "signature": _draw_signature(index_stream, vertex_buffers),
    }


def _normalise_events(event_id, event_ids):
    """Return an ordered list of int event ids from either spelling.

    Accepts an int, a list/tuple in ``event_id``, or ``event_ids``; caller
    order is preserved.
    """
    if event_ids is not None:
        if event_id is not None:
            raise MeshExportError("pass either event_id or event_ids, not both")
        source = event_ids
    elif event_id is not None:
        source = event_id
    else:
        raise MeshExportError("export_mesh needs an event_id or an event_ids list")

    if isinstance(source, (list, tuple)):
        events = [int(e) for e in source]
    else:
        events = [int(source)]
    if not events:
        raise MeshExportError("export_mesh was given no events")
    return events


# Suggested spec for merged export; quoted back when the caller omits one.
_MULTI_EXAMPLE_SPEC = "pos=_input0.xyz,uv=_input1.xy,normal=normal(_input2)"


def export_mesh(
    event_id=None,
    columns=None,
    name=None,
    out_dir=None,
    bridge=None,
    event_ids=None,
    dedup_draws=True,
    dedup_vertices=False,
):
    """Decode one or more draws and write CSV + OBJ files.

    Single event (``event_id``, or a one-element ``event_ids``) behaves exactly
    as before: ``columns=None`` exports every attribute/component as raw
    columns.

    Merged export (``event_ids`` with more than one entry) requires an explicit
    ``columns`` spec -- the default column set is invented per event and cannot
    be concatenated.  Each event is decoded in order against the same spec; the
    CSV rows are concatenated (indices remapped by the running vertex offset)
    while the OBJ writes one ``o ev<event_id>`` section per kept event.

    Args:
        event_id: one draw's event id (an int, or a list of ints).
        columns: comma-separated column spec (see :func:`parse_columns`);
            mandatory for merged export.
        name: file basename (default ``mesh_<event_id>``, or
            ``mesh_<first>_<last>`` when merged).
        out_dir: output directory (default ``<repo root>/Output``).
        bridge: optional pre-built :class:`RenderDocBridge`.
        event_ids: list of event ids to merge; mutually exclusive with
            ``event_id``.
        dedup_draws: drop later events whose index/vertex bindings *and*
            decoded data match an earlier kept event (default ``True``).
        dedup_vertices: accepted for backwards compatibility and ignored (no
            warning) for merged export, where every event keeps its own
            vertices as a separate OBJ object.

    Returns the written paths, counts, column names and merged position bbox.
    Merged export additionally reports ``event_ids`` (kept, in order),
    ``duplicates`` (``{event_id, duplicate_of}``) and ``per_event``
    (``{event_id, vertex_count, triangle_count, vertex_offset}``).  In the
    merged OBJ each event is an ``o ev<event_id>`` section, and an event's
    ``vertex_offset`` is also the base index minus one of its object's faces.
    """
    if bridge is None:
        bridge = RenderDocBridge()

    events = _normalise_events(event_id, event_ids)
    merged = len(events) > 1

    if merged and columns is None:
        raise MeshExportError(
            "merged export needs an explicit columns spec: the default column "
            "set differs per event and cannot be concatenated.  Pass e.g. %r"
            % _MULTI_EXAMPLE_SPEC
        )

    if name is None:
        name = (
            "mesh_%s_%s" % (events[0], events[-1]) if merged else "mesh_%s" % events[0]
        )
    out_dir = out_dir or DEFAULT_OUT_DIR
    os.makedirs(out_dir, exist_ok=True)

    warnings = []
    records = [
        _decode_event(bridge, event, columns, warnings, name_errors=merged)
        for event in events
    ]

    if not merged:
        record = records[0]
        vertices_csv, flat_names = _write_vertices_csv(
            out_dir, name, record["decoded"], record["vertex_count"]
        )
        indices_csv, triangle_count = _write_indices_csv(
            out_dir, name, record["indices"]
        )
        obj_path, bbox = _write_obj(
            out_dir, name, record["decoded"], record["indices"], triangle_count, warnings
        )
        # Guarded on the OBJ path: both writers need a position column, so this
        # keeps the "no position column" warning to a single line.
        usda_path = None
        if obj_path is not None:
            usda_path, _ = _write_usda(
                out_dir,
                name,
                record["decoded"],
                record["indices"],
                triangle_count,
                warnings,
                event_id=record["event_id"],
            )
        return {
            "vertices_csv": vertices_csv,
            "indices_csv": indices_csv,
            "obj": obj_path,
            "usda": usda_path,
            "vertex_count": record["vertex_count"],
            "triangle_count": triangle_count,
            "columns": flat_names,
            "bbox": bbox,
            "base_vertex": record["base_vertex"],
            "warnings": warnings,
        }

    # --- drop duplicate draws ----------------------------------------------
    kept = []
    duplicates = []
    seen = {}
    for record in records:
        signature = record["signature"]
        first = seen.get(signature) if dedup_draws else None
        if first is not None:
            if _same_decoded(record, first):
                duplicates.append(
                    {"event_id": record["event_id"], "duplicate_of": first["event_id"]}
                )
                continue
            warnings.append(
                "event %s shares its draw signature with event %s but decodes "
                "differently; keeping both" % (record["event_id"], first["event_id"])
            )
        if dedup_draws:
            seen.setdefault(signature, record)
        kept.append(record)

    # --- merge --------------------------------------------------------------
    columns_count = len(kept[0]["decoded"])
    merged_values = [[] for _ in range(columns_count)]
    merged_indices = []
    per_event = []
    vertex_offset = 0
    for record in kept:
        for index, entry in enumerate(record["decoded"]):
            merged_values[index].extend(entry["values"])
        merged_indices.extend(i + vertex_offset for i in record["indices"])
        per_event.append(
            {
                "event_id": record["event_id"],
                "vertex_count": record["vertex_count"],
                "triangle_count": len(record["indices"]) // 3,
                "vertex_offset": vertex_offset,
            }
        )
        vertex_offset += record["vertex_count"]

    # A merged OBJ gives each event its own object with its own vertices, so
    # cross-event vertex de-duplication has no meaning here.  ``dedup_vertices``
    # is deliberately ignored (without a warning) for multi-event export.
    vertex_count = len(merged_values[0]) if columns_count else 0

    first_decoded = kept[0]["decoded"]
    decoded = [
        {
            "column": first_decoded[index]["column"],
            "labels": first_decoded[index]["labels"],
            "is_int": first_decoded[index]["is_int"],
            "values": merged_values[index],
        }
        for index in range(columns_count)
    ]

    vertices_csv, flat_names = _write_vertices_csv(
        out_dir, name, decoded, vertex_count
    )
    indices_csv, triangle_count = _write_indices_csv(out_dir, name, merged_indices)
    obj_path, bbox = _write_obj_merged(out_dir, name, kept, warnings)
    usda_path = None
    if obj_path is not None:
        usda_path, _ = _write_usda_merged(out_dir, name, kept, warnings)

    # Indices already carry each event's base vertex and its running offset, so
    # there is no single merged base vertex left to report.
    return {
        "vertices_csv": vertices_csv,
        "indices_csv": indices_csv,
        "obj": obj_path,
        "usda": usda_path,
        "vertex_count": vertex_count,
        "triangle_count": triangle_count,
        "columns": flat_names,
        "bbox": bbox,
        "base_vertex": 0,
        "warnings": warnings,
        "event_ids": [record["event_id"] for record in kept],
        "duplicates": duplicates,
        "per_event": per_event,
    }
