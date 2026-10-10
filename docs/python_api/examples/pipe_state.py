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

pipe = pydhr.CurPipelineState()

get_name = lambda id: pydhr.GetResourceName(id)

print("-------------------------")
print("        Outputs          ")
print("-------------------------")

# list all the output targets
outs = pipe.GetOutputTargets()
for i, out in enumerate(outs):
    id = out.resource
    # ignore any targets that are unbound
    if id != dhr.ResourceId():
        print(f"Out {i}: {get_name(id)}")

id = pipe.GetDepthTarget().resource
print(f"Depth: {get_name(id)}")

print()
print("-------------------------")
print("     Pipeline/Shaders    ")
print("-------------------------")

id = pipe.GetGraphicsPipelineObject()
print(f"Pipeline: {get_name(id)}")

id = pipe.GetShader(dhr.ShaderStage.Vertex)
print(f"VS: {get_name(id)}")
id = pipe.GetShader(dhr.ShaderStage.Pixel)
print(f"PS: {get_name(id)}")

print()
print("-------------------------")
print("   Constant Blocks (VS)  ")
print("-------------------------")

cbs = pipe.GetConstantBlocks(dhr.ShaderStage.Vertex)

# print out the stage even though we've asked for vertex CBs.
# the index corresponds to which constant block in the vertex
# reflection was used (omitted here is the array index which
# doesn't affect that lookup)
for cb in cbs:
    print(
        f"{str(cb.access.stage)} CB[{cb.access.index}]: {get_name(cb.descriptor.resource)}"
    )

print()
print("-------------------------")
print("   Descriptors by Stage  ")
print("-------------------------")

# ask for all descriptors but only those that are used
descs = pipe.GetAllUsedDescriptors(True)

# first we'll iterate over all possible shader stages, and get all
# the descriptors for that stage
for stage in dhr.ShaderStage:
    # silently skip stages with no used bindings
    stage_descs = [d for d in descs if d.access.stage == stage]
    if stage_descs == []:
        continue

    # now iterate over the descriptors and print its type and the resources
    # in the descriptor
    print(f"** {str(stage)} descriptors:")
    for d in stage_descs:
        desc_str = f"{str(d.access.type)} - "
        if (
            d.sampler.object != dhr.ResourceId()
            and d.descriptor.resource != dhr.ResourceId()
        ):
            desc_str += (
                f"{get_name(d.descriptor.resource)} + {get_name(d.sampler.object)}"
            )
        elif d.sampler.object != dhr.ResourceId():
            desc_str += f"{get_name(d.sampler.object)}"
        else:
            desc_str += f"{get_name(d.descriptor.resource)}"
        print(desc_str)

        # we also print the descriptor store this is stored in
        print(
            f"  in {get_name(d.access.descriptorStore)} at offset {d.access.byteOffset}"
        )

print()
print("-------------------------")
print("   Descriptors by Type   ")
print("-------------------------")

# Iterate in a similar way, but this time grouping by descriptor type
for desctype in dhr.DescriptorType:
    type_descs = [d for d in descs if d.access.type == desctype]
    if type_descs == []:
        continue

    print(f"** {str(desctype)} descriptors:")
    for d in type_descs:
        desc_str = f"{str(d.access.stage)} - "
        if (
            d.sampler.object != dhr.ResourceId()
            and d.descriptor.resource != dhr.ResourceId()
        ):
            desc_str += (
                f"{get_name(d.descriptor.resource)} + {get_name(d.sampler.object)}"
            )
        elif d.sampler.object != dhr.ResourceId():
            desc_str += f"{get_name(d.sampler.object)}"
        else:
            desc_str += f"{get_name(d.descriptor.resource)}"
        print(desc_str)

        print(
            f"  in {get_name(d.access.descriptorStore)} at offset {d.access.byteOffset}"
        )
