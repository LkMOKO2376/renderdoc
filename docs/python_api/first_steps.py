if not pydhr.IsCaptureLoaded():
    filename = pydhr.Extensions().OpenFileName("Choose a capture", "", "*.rdc")

    pydhr.LoadCapture(filename, dhr.ReplayOptions(), filename, False, True)

eid = pydhr.CurEvent()

name = pydhr.GetEventBrowser().GetEventName(eid)

print(f"Currently we are at EID {eid} named: '{name}'")
if eid > 1:
    prevname = pydhr.GetEventBrowser().GetEventName(eid - 1)
    print(f"    > the previous event {eid-1} is named: '{prevname}'")

pipe = pydhr.CurPipelineState()

outputs = pipe.GetOutputTargets()

for idx, out in enumerate(outputs):
    if out.resource != dhr.ResourceId.Null():
        name = pydhr.GetResourceName(out.resource)
        print(f"Output {idx} is: {name}")

depth = pipe.GetDepthTarget()

name = pydhr.GetResourceName(depth.resource)
print(f"Depth is: {name}")