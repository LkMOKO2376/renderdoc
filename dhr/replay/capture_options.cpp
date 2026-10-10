/******************************************************************************
 * The MIT License (MIT)
 *
 * Copyright (c) 2015-2026 Baldur Karlsson
 *
 * Permission is hereby granted, free of charge, to any person obtaining a copy
 * of this software and associated documentation files (the "Software"), to deal
 * in the Software without restriction, including without limitation the rights
 * to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
 * copies of the Software, and to permit persons to whom the Software is
 * furnished to do so, subject to the following conditions:
 *
 * The above copyright notice and this permission notice shall be included in
 * all copies or substantial portions of the Software.
 *
 * THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
 * IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
 * FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
 * AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
 * LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
 * OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
 * THE SOFTWARE.
 ******************************************************************************/

#include "api/replay/capture_options.h"
#include <float.h>
#include "api/app/dhr_app.h"
#include "common/common.h"
#include "core/core.h"

int DHR_CC SetCaptureOptionU32(DHR_CaptureOption opt, uint32_t val)
{
  CaptureOptions opts = DHR::Inst().GetCaptureOptions();

  switch(opt)
  {
    case eDHR_Option_AllowVSync: opts.allowVSync = (val != 0); break;
    case eDHR_Option_AllowFullscreen: opts.allowFullscreen = (val != 0); break;
    case eDHR_Option_APIValidation: opts.apiValidation = (val != 0); break;
    case eDHR_Option_CaptureCallstacks: opts.captureCallstacks = (val != 0); break;
    case eDHR_Option_CaptureCallstacksOnlyDraws:
      opts.captureCallstacksOnlyActions = (val != 0);
      break;
    case eDHR_Option_DelayForDebugger: opts.delayForDebugger = val; break;
    case eDHR_Option_VerifyBufferAccess: opts.verifyBufferAccess = (val != 0); break;
    case eDHR_Option_HookIntoChildren: opts.hookIntoChildren = (val != 0); break;
    case eDHR_Option_RefAllResources: opts.refAllResources = (val != 0); break;
    case eDHR_Option_SaveAllInitials:
      // option is deprecated
      break;
    case eDHR_Option_CaptureAllCmdLists: opts.captureAllCmdLists = (val != 0); break;
    case eDHR_Option_DebugOutputMute: opts.debugOutputMute = (val != 0); break;
    case eDHR_Option_AllowUnsupportedVendorExtensions:
      if(val == 0x10DE)
        DHR::Inst().EnableVendorExtensions(VendorExtensions::NvAPI);
      else
        RDCWARN("AllowUnsupportedVendorExtensions unexpected parameter %x", val);
      break;
    case eDHR_Option_SoftMemoryLimit: opts.softMemoryLimit = val; break;
    default: RDCLOG("Unrecognised capture option '%d'", opt); return 0;
  }

  DHR::Inst().SetCaptureOptions(opts);
  return 1;
}

int DHR_CC SetCaptureOptionF32(DHR_CaptureOption opt, float val)
{
  CaptureOptions opts = DHR::Inst().GetCaptureOptions();

  switch(opt)
  {
    case eDHR_Option_AllowVSync: opts.allowVSync = (val != 0.0f); break;
    case eDHR_Option_AllowFullscreen: opts.allowFullscreen = (val != 0.0f); break;
    case eDHR_Option_APIValidation: opts.apiValidation = (val != 0.0f); break;
    case eDHR_Option_CaptureCallstacks: opts.captureCallstacks = (val != 0.0f); break;
    case eDHR_Option_CaptureCallstacksOnlyDraws:
      opts.captureCallstacksOnlyActions = (val != 0.0f);
      break;
    case eDHR_Option_DelayForDebugger: opts.delayForDebugger = (uint32_t)val; break;
    case eDHR_Option_VerifyBufferAccess: opts.verifyBufferAccess = (val != 0.0f); break;
    case eDHR_Option_HookIntoChildren: opts.hookIntoChildren = (val != 0.0f); break;
    case eDHR_Option_RefAllResources: opts.refAllResources = (val != 0.0f); break;
    case eDHR_Option_SaveAllInitials:
      // option is deprecated
      break;
    case eDHR_Option_CaptureAllCmdLists: opts.captureAllCmdLists = (val != 0.0f); break;
    case eDHR_Option_DebugOutputMute: opts.debugOutputMute = (val != 0.0f); break;
    case eDHR_Option_AllowUnsupportedVendorExtensions:
      RDCWARN("AllowUnsupportedVendorExtensions unexpected parameter %f", val);
      break;
    case eDHR_Option_SoftMemoryLimit: opts.softMemoryLimit = (uint32_t)val; break;
    default: RDCLOG("Unrecognised capture option '%d'", opt); return 0;
  }

  DHR::Inst().SetCaptureOptions(opts);
  return 1;
}

uint32_t DHR_CC GetCaptureOptionU32(DHR_CaptureOption opt)
{
  switch(opt)
  {
    case eDHR_Option_AllowVSync:
      return (DHR::Inst().GetCaptureOptions().allowVSync ? 1 : 0);
    case eDHR_Option_AllowFullscreen:
      return (DHR::Inst().GetCaptureOptions().allowFullscreen ? 1 : 0);
    case eDHR_Option_APIValidation:
      return (DHR::Inst().GetCaptureOptions().apiValidation ? 1 : 0);
    case eDHR_Option_CaptureCallstacks:
      return (DHR::Inst().GetCaptureOptions().captureCallstacks ? 1 : 0);
    case eDHR_Option_CaptureCallstacksOnlyDraws:
      return (DHR::Inst().GetCaptureOptions().captureCallstacksOnlyActions ? 1 : 0);
    case eDHR_Option_DelayForDebugger:
      return (DHR::Inst().GetCaptureOptions().delayForDebugger);
    case eDHR_Option_VerifyBufferAccess:
      return (DHR::Inst().GetCaptureOptions().verifyBufferAccess ? 1 : 0);
    case eDHR_Option_HookIntoChildren:
      return (DHR::Inst().GetCaptureOptions().hookIntoChildren ? 1 : 0);
    case eDHR_Option_RefAllResources:
      return (DHR::Inst().GetCaptureOptions().refAllResources ? 1 : 0);
    case eDHR_Option_SaveAllInitials:
      // option is deprecated - always enabled
      return 1;
    case eDHR_Option_CaptureAllCmdLists:
      return (DHR::Inst().GetCaptureOptions().captureAllCmdLists ? 1 : 0);
    case eDHR_Option_DebugOutputMute:
      return (DHR::Inst().GetCaptureOptions().debugOutputMute ? 1 : 0);
    case eDHR_Option_AllowUnsupportedVendorExtensions: return 0;
    case eDHR_Option_SoftMemoryLimit:
      return (DHR::Inst().GetCaptureOptions().softMemoryLimit);
    default: break;
  }

  RDCLOG("Unrecognised capture option '%d'", opt);
  return 0xffffffff;
}

float DHR_CC GetCaptureOptionF32(DHR_CaptureOption opt)
{
  switch(opt)
  {
    case eDHR_Option_AllowVSync:
      return (DHR::Inst().GetCaptureOptions().allowVSync ? 1.0f : 0.0f);
    case eDHR_Option_AllowFullscreen:
      return (DHR::Inst().GetCaptureOptions().allowFullscreen ? 1.0f : 0.0f);
    case eDHR_Option_APIValidation:
      return (DHR::Inst().GetCaptureOptions().apiValidation ? 1.0f : 0.0f);
    case eDHR_Option_CaptureCallstacks:
      return (DHR::Inst().GetCaptureOptions().captureCallstacks ? 1.0f : 0.0f);
    case eDHR_Option_CaptureCallstacksOnlyDraws:
      return (DHR::Inst().GetCaptureOptions().captureCallstacksOnlyActions ? 1.0f : 0.0f);
    case eDHR_Option_DelayForDebugger:
      return (DHR::Inst().GetCaptureOptions().delayForDebugger * 1.0f);
    case eDHR_Option_VerifyBufferAccess:
      return (DHR::Inst().GetCaptureOptions().verifyBufferAccess ? 1.0f : 0.0f);
    case eDHR_Option_HookIntoChildren:
      return (DHR::Inst().GetCaptureOptions().hookIntoChildren ? 1.0f : 0.0f);
    case eDHR_Option_RefAllResources:
      return (DHR::Inst().GetCaptureOptions().refAllResources ? 1.0f : 0.0f);
    case eDHR_Option_SaveAllInitials:
      // option is deprecated - always enabled
      return 1.0f;
    case eDHR_Option_CaptureAllCmdLists:
      return (DHR::Inst().GetCaptureOptions().captureAllCmdLists ? 1.0f : 0.0f);
    case eDHR_Option_DebugOutputMute:
      return (DHR::Inst().GetCaptureOptions().debugOutputMute ? 1.0f : 0.0f);
    case eDHR_Option_AllowUnsupportedVendorExtensions: return 0.0f;
    case eDHR_Option_SoftMemoryLimit:
      return (DHR::Inst().GetCaptureOptions().softMemoryLimit * 1.0f);
    default: break;
  }

  RDCLOG("Unrecognised capture option '%d'", opt);
  return -FLT_MAX;
}

#if ENABLED(ENABLE_UNIT_TESTS)

#undef None
#undef Always

#include "catch/catch.hpp"

TEST_CASE("Check CaptureOptions de/serialise to string", "[serialise]")
{
  CaptureOptions opts;

  bool *boolOpts[] = {
      &opts.allowVSync,
      &opts.allowFullscreen,
      &opts.apiValidation,
      &opts.captureCallstacks,
      &opts.captureCallstacksOnlyActions,
      &opts.verifyBufferAccess,
      &opts.hookIntoChildren,
      &opts.refAllResources,
      &opts.captureAllCmdLists,
      &opts.debugOutputMute,
  };

  for(uint32_t delay = 0; delay < 1000; delay++)
  {
    for(uint32_t variant = 0; variant < (1 << ARRAY_COUNT(boolOpts)); variant++)
    {
      opts.delayForDebugger = delay;
      for(size_t o = 0; o < ARRAY_COUNT(boolOpts); o++)
      {
        *boolOpts[o] = (variant & (1 << o)) != 0;
      }

      rdcstr s = opts.EncodeAsString();
      CaptureOptions decoded;
      decoded.DecodeFromString(s);

      CHECK(memcmp(&opts, &decoded, sizeof(decoded)) == 0);
    }
  }

  // check that nothing explodes here
  CaptureOptions a;
  a.DecodeFromString("");
}

#endif
