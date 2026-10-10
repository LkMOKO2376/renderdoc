import struct

# these imports are not strictly necessary, but are convenient
import dhr
import qdhr

# this is here to give autocomplete when editing the example
# in VS Code where it doesn't know about this global
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pydhr = qdhr.CaptureContext()

if not pydhr.IsCaptureLoaded():
    filename = pydhr.Extensions().OpenFileName("Choose a capture", "", "*.rdc")

    pydhr.LoadCapture(filename, dhr.ReplayOptions(), filename, False, True)

mybuf = dhr.ResourceId.Null()

for buf in pydhr.GetBuffers():
    print(f"buf {buf.resourceId} is {pydhr.GetResourceName(buf.resourceId)}")

    mybuf = buf.resourceId

    # here put your actual selection criteria - i.e. look for a particular name
    if "Vertex" in pydhr.GetResourceName(buf.resourceId):
        break

print(f"selected {pydhr.GetResourceName(mybuf)}")

formatter = """
float3 pos;
half norms[6];
uint flags;
"""

if mybuf != dhr.ResourceId.Null():
    # Open a new buffer viewer for this buffer, with the given format
    bufview = pydhr.ViewBuffer(0, 0, mybuf, formatter)

    # Show the buffer viewer on the main tool area
    pydhr.AddDockWindow(
        bufview.Widget(), qdhr.DockReference.MainToolArea, None
    )

    # Get access to a controller to get the buffer data.
    # We use the blocking controller for simplicity, but a better option
    # might be to invoke onto the replay thread with
    # pydhr.Replay().AsyncInvoke()
    controller = pydhr.GetBlockingController()

    data_bytes = controller.GetBufferData(mybuf, 0, 8)

    data_decoded = struct.unpack_from("8B", data_bytes)

    print(f"The first 8 bytes of the buffer are: {data_decoded}")
