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

# prime numbers have exactly 2 integer factors.
# note the // operator in python does integer-division
def isprime(n):
    return len([x for x in range(1, n + 1) if (n / x) == (n // x)]) == 2


# our main filter function. Could use the params or other things passed in
# to do more complex filtering
def filter_func(
    ctx: qdhr.CaptureContext,
    filter: str,
    params: str,
    eventId: int,
    chunk: dhr.SDChunk,
    action: dhr.ActionDescription,
    eventName: str,
):
    return isprime(eventId)


# the parser gives us a chance to parse the params and cache the data,
# this is only called when the filter is modified. It also lets us
# error-check any params we want
def parser_func(ctx: qdhr.CaptureContext, filter: str, params: str):
    if "error" in params:
        return f"You shouldn't put 'error' in ${filter}()"
    return ""


# the completer can take the current params string and dynamically
# provide auto-complete suggestions for what to add.
def completer_func(ctx: qdhr.CaptureContext, filter: str, params: str):
    return ["foo", "bar", "error"]


# In a UI extension we'd register and unregister over the lifetime of the extension.
# But we can also just unregister unconditionally, and then re-register. Note if you
# do not unregister then this will fail and will refuse to overwrite an existing filter.
pydhr.GetEventBrowser().UnregisterEventFilterFunction("prime")
pydhr.GetEventBrowser().RegisterEventFilterFunction(
    "prime",
    "Show only events with prime EIDs.",
    filter_func,
    parser_func,
    completer_func,
)
