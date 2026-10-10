/******************************************************************************
 * The MIT License (MIT)
 *
 * Copyright (c) 2015-2026 Baldur Karlsson
 * Copyright (c) 2014 Crytek
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

#include "dhrcmd.h"
#include <app/dhr_app.h>
#include <dhrshim.h>
#include <windows.h>
#include <string>
#include <vector>
#include "miniz/miniz.h"
#include "resource.h"

#include <Psapi.h>
#include <shldisp.h>
#include <shlobj.h>
#include <tlhelp32.h>

#include <algorithm>
#include <cwctype>
#include <set>

static std::string conv(const std::wstring &str)
{
  std::string ret;
  // worst case each char takes 4 bytes to encode
  ret.resize(str.size() * 4 + 1);

  WideCharToMultiByte(CP_UTF8, 0, str.c_str(), -1, &ret[0], (int)ret.size(), NULL, NULL);

  ret.resize(strlen(ret.c_str()));

  return ret;
}

static std::wstring conv(const std::string &str)
{
  std::wstring ret;
  ret.resize(str.size() + 1);

  MultiByteToWideChar(CP_UTF8, 0, str.c_str(), -1, &ret[0], int(ret.size() + 1));

  ret.resize(wcslen(ret.c_str()));

  return ret;
}

HINSTANCE hInstance = NULL;

#if defined(RELEASE) && DHR_OFFICIAL_BUILD
#define CRASH_HANDLER 1
#else
#define CRASH_HANDLER 0
#endif

#if CRASH_HANDLER
// breakpad
#include "breakpad/client/windows/crash_generation/client_info.h"
#include "breakpad/client/windows/crash_generation/crash_generation_server.h"
#include "breakpad/common/windows/http_upload.h"

using google_breakpad::ClientInfo;
using google_breakpad::CrashGenerationServer;

bool clientConnected = false;
bool exitServer = false;

std::wstring wdump = L"";
std::vector<google_breakpad::CustomInfoEntry> customInfo;

static void _cdecl OnClientConnected(void *context, const ClientInfo *client_info)
{
  clientConnected = true;
}

static void _cdecl OnClientCrashed(void *context, const ClientInfo *client_info,
                                   const std::wstring *dump_path)
{
  if(dump_path)
  {
    wdump = *dump_path;

    google_breakpad::CustomClientInfo custom = client_info->GetCustomInfo();

    for(size_t i = 0; i < custom.count; i++)
      customInfo.push_back(custom.entries[i]);
  }

  exitServer = true;
}

static void _cdecl OnClientExited(void *context, const ClientInfo *client_info)
{
  exitServer = true;
}
#endif

LRESULT CALLBACK WndProc(HWND hwnd, UINT msg, WPARAM wParam, LPARAM lParam)
{
  if(msg == WM_CLOSE)
  {
    DestroyWindow(hwnd);
    return 0;
  }
  if(msg == WM_DESTROY)
  {
    PostQuitMessage(0);
    return 0;
  }
  return DefWindowProc(hwnd, msg, wParam, lParam);
}

void Daemonise()
{
  // nothing really to do, windows version of dhrcmd is already 'detached'
}

WindowingData DisplayRemoteServerPreview(bool active, const rdcarray<WindowingSystem> &systems)
{
  static WindowingData remoteServerPreview = {WindowingSystem::Unknown};

  if(active)
  {
    if(remoteServerPreview.system == WindowingSystem::Unknown)
    {
      // if we're first initialising, create the window

      RECT wr = {0, 0, (LONG)1280, (LONG)720};
      AdjustWindowRect(&wr, WS_OVERLAPPEDWINDOW, FALSE);

      HWND wnd =
          CreateWindowEx(WS_EX_CLIENTEDGE, L"dhrcmd", L"Remote Server Preview",
                         WS_OVERLAPPED | WS_CAPTION | WS_MINIMIZEBOX, CW_USEDEFAULT, CW_USEDEFAULT,
                         wr.right - wr.left, wr.bottom - wr.top, NULL, NULL, hInstance, NULL);

      if(wnd == NULL)
        return remoteServerPreview;

      ShowWindow(wnd, SW_SHOW);
      UpdateWindow(wnd);

      remoteServerPreview.system = WindowingSystem::Win32;
      remoteServerPreview.win32.window = wnd;
    }
    else
    {
      // otherwise, pump messages
      MSG msg;
      ZeroMemory(&msg, sizeof(msg));

      // Check to see if any messages are waiting in the queue
      while(PeekMessage(&msg, NULL, 0, 0, PM_REMOVE))
      {
        // Translate the message and dispatch it to WindowProc()
        TranslateMessage(&msg);
        DispatchMessage(&msg);
      }
    }
  }
  else
  {
    // if we had a previous window, destroy it.
    if(remoteServerPreview.win32.window != NULL)
      DestroyWindow(remoteServerPreview.win32.window);

    // reset the windowing data to 'no window'
    remoteServerPreview = {WindowingSystem::Unknown};
  }

  return remoteServerPreview;
}

void DisplayRendererPreview(IReplayController *renderer, TextureDisplay &displayCfg, uint32_t width,
                            uint32_t height, uint32_t numLoops)
{
  RECT wr = {0, 0, (LONG)width, (LONG)height};
  AdjustWindowRect(&wr, WS_OVERLAPPEDWINDOW, FALSE);

  HWND wnd = CreateWindowEx(WS_EX_CLIENTEDGE, L"dhrcmd", L"dhrcmd", WS_OVERLAPPEDWINDOW,
                            CW_USEDEFAULT, CW_USEDEFAULT, wr.right - wr.left, wr.bottom - wr.top,
                            NULL, NULL, hInstance, NULL);

  if(wnd == NULL)
    return;

  ShowWindow(wnd, SW_SHOW);
  UpdateWindow(wnd);

  IReplayOutput *out =
      renderer->CreateOutput(CreateWin32WindowingData(wnd), ReplayOutputType::Texture);

  out->SetTextureDisplay(displayCfg);

  uint32_t loopCount = 0;

  MSG msg;
  ZeroMemory(&msg, sizeof(msg));
  while(true)
  {
    // Check to see if any messages are waiting in the queue
    while(PeekMessage(&msg, NULL, 0, 0, PM_REMOVE))
    {
      // Translate the message and dispatch it to WindowProc()
      TranslateMessage(&msg);
      DispatchMessage(&msg);
    }

    // If the message is WM_QUIT, exit the while loop
    if(msg.message == WM_QUIT)
      break;

    // set to random event beyond the end of the frame to ensure output is marked as dirty
    renderer->SetFrameEvent(10000000, true);
    out->Display();

    Sleep(40);

    loopCount++;

    if(numLoops > 0 && loopCount == numLoops)
      break;
  }

  DestroyWindow(wnd);
}

struct UpgradeCommand : public Command
{
private:
  std::wstring wide_path;
  bool dryrun = false;

public:
  UpgradeCommand() {}
  virtual void AddOptions(cmdline::parser &parser)
  {
    parser.add<std::string>("path", 0, "");
    parser.add("dryrun", '\0', "");
  }
  virtual const char *Description() { return "Internal use only!"; }
  virtual bool IsInternalOnly() { return true; }
  virtual bool IsCaptureCommand() { return false; }
  virtual bool Parse(cmdline::parser &parser, GlobalEnvironment &)
  {
    wide_path = conv(parser.get<std::string>("path"));
    dryrun = parser.exist("dryrun");
    return true;
  }

  virtual int Execute(const CaptureOptions &)
  {
    if(wide_path.back() != '\\' && wide_path.back() != '/')
      wide_path += L'\\';

    CoInitialize(NULL);

    // Wait for UI to exit
    Sleep(3000);

    mz_zip_archive zip;
    ZeroMemory(&zip, sizeof(zip));

    bool successful = false;
    std::wstring failReason = L"\"Unknown error\"";

    mz_bool b = mz_zip_reader_init_file(&zip, "./update.zip", 0);

    if(dryrun)
    {
      successful = true;
    }
    else if(b)
    {
      mz_uint numfiles = mz_zip_reader_get_num_files(&zip);

      // first create directories
      for(mz_uint i = 0; i < numfiles; i++)
      {
        if(mz_zip_reader_is_file_a_directory(&zip, i))
        {
          mz_zip_archive_file_stat zstat;
          mz_zip_reader_file_stat(&zip, i, &zstat);

          const char *fn = zstat.m_filename;
          // skip first directory because it's DHR_Version_Bitness/
          fn = strchr(fn, '/');
          if(fn)
            fn++;

          if(fn && *fn)
          {
            wchar_t conv[MAX_PATH] = {0};
            wchar_t *wfn = conv;

            // I know the zip only contains ASCII chars, just upcast
            while(*fn)
              *(wfn++) = wchar_t(*(fn++));

            std::wstring target = wide_path + conv;

            wfn = &target[0];

            // convert slashes because CreateDirectory barfs on
            // proper slashes.
            while(*(wfn++))
            {
              if(*wfn == L'/')
                *wfn = L'\\';
            }

            CreateDirectoryW(target.c_str(), NULL);
          }
        }
      }

      // next make sure we can get read+write access to every file. If not
      // one might be in use, but we definitely can't update it
      successful = true;

      for(mz_uint i = 0; successful && i < numfiles; i++)
      {
        if(!mz_zip_reader_is_file_a_directory(&zip, i))
        {
          mz_zip_archive_file_stat zstat;
          mz_zip_reader_file_stat(&zip, i, &zstat);

          const char *fn = zstat.m_filename;
          // skip first directory because it's DHR_Version_Bitness/
          fn = strchr(fn, '/');
          if(fn)
            fn++;

          if(fn && *fn)
          {
            wchar_t conv[MAX_PATH] = {0};
            wchar_t *wfn = conv;

            // I know the zip only contains ASCII chars, just upcast
            while(*fn)
              *(wfn++) = wchar_t(*(fn++));

            std::wstring target = wide_path + conv;

            wfn = &target[0];

            // convert slashes just to be consistent
            while(*(wfn++))
            {
              if(*wfn == L'/')
                *wfn = L'\\';
            }

            FILE *f = NULL;
            _wfopen_s(&f, target.c_str(), L"a+");
            if(!f)
            {
              failReason = L"\"Couldn't modify an install file - likely file is in use.\"";
              successful = false;
            }
            else
            {
              fclose(f);
            }
          }
        }
      }

      for(mz_uint i = 0; successful && i < numfiles; i++)
      {
        if(!mz_zip_reader_is_file_a_directory(&zip, i))
        {
          mz_zip_archive_file_stat zstat;
          mz_zip_reader_file_stat(&zip, i, &zstat);

          const char *fn = zstat.m_filename;
          // skip first directory because it's DHR_Version_Bitness/
          fn = strchr(fn, '/');
          if(fn)
            fn++;

          if(fn && *fn)
          {
            wchar_t conv[MAX_PATH] = {0};
            wchar_t *wfn = conv;

            // I know the zip only contains ASCII chars, just upcast
            while(*fn)
              *(wfn++) = wchar_t(*(fn++));

            std::wstring target = wide_path + conv;

            wfn = &target[0];

            // convert slashes just to be consistent
            while(*(wfn++))
            {
              if(*wfn == L'/')
                *wfn = L'\\';
            }

            FILE *target_file = NULL;
            _wfopen_s(&target_file, target.c_str(), L"wb");
            if(target_file)
            {
              mz_zip_reader_extract_to_cfile(&zip, i, target_file, 0);
              fclose(target_file);
            }
          }
        }
      }
    }
    else
    {
      failReason = L"\"Failed to open update .zip file - possibly corrupted.\"";
    }

    // run original UI exe (as admin still) and tell it an update succeeded so that it can do any last updates
    std::wstring cmdline = L"\"";
    cmdline += wide_path;
    cmdline += L"/qdhr.exe\" ";
    if(successful)
      cmdline += L"--updatedone_admin";
    else
      cmdline += L"--updatefailed " + failReason;

    wchar_t *paramsAlloc = new wchar_t[512];

    ZeroMemory(paramsAlloc, sizeof(wchar_t) * 512);

    wcscpy_s(paramsAlloc, 511, cmdline.c_str());

    PROCESS_INFORMATION pi;
    STARTUPINFOW si;
    ZeroMemory(&pi, sizeof(pi));
    ZeroMemory(&si, sizeof(si));

    CreateProcessW(NULL, paramsAlloc, NULL, NULL, FALSE, 0, NULL, NULL, &si, &pi);

    if(pi.dwProcessId != 0)
    {
      CloseHandle(pi.hProcess);
      CloseHandle(pi.hThread);
    }

    // try to launch the UI as a regular user again

    // from https://devblogs.microsoft.com/oldnewthing/?p=2643
    // Old New Thing "How can I launch an unelevated process from my elevated process and vice
    // versa?" November 18th, 2013 for when that blog link inevitably breaks

    // we deliberately don't try to release any of these objects - they will just leak as we're
    // going to exit in a moment either way

    IShellWindows *shellWindows = NULL;
    if(SUCCEEDED(CoCreateInstance(CLSID_ShellWindows, NULL, CLSCTX_ALL, IID_IShellWindows,
                                  (void **)&shellWindows)))
    {
      // documentation for FindWindowSW says location must be VT_VARIANT | VT_BYREF but this is what
      // the examples do and it works
      VARIANT location = {};
      location.vt = VT_I4;
      location.lVal = CSIDL_DESKTOP;

      VARIANT empty = {};
      long hwnd = 0;

      IDispatch *spdisp = NULL;
      if(SUCCEEDED(shellWindows->FindWindowSW(&location, &empty, SWC_DESKTOP, &hwnd,
                                              SWFO_NEEDDISPATCH, &spdisp)))
      {
        // go through the chain of interfaces to get explorer's dispatch helper
        IServiceProvider *querier = NULL;
        IShellBrowser *spBrowser = NULL;
        IShellView *spView = NULL;
        IShellView *spsv = NULL;
        IDispatch *spdispView = NULL;
        IShellFolderViewDual *spFolderView = NULL;
        IDispatch *spdispShell = NULL;
        IShellDispatch2 *dispatcher = NULL;
        if(SUCCEEDED(spdisp->QueryInterface(__uuidof(IServiceProvider), (void **)&querier)) &&
           SUCCEEDED(querier->QueryService(SID_STopLevelBrowser, __uuidof(IShellBrowser),
                                           (void **)&spBrowser)) &&
           SUCCEEDED(spBrowser->QueryActiveShellView(&spView)) &&
           SUCCEEDED(spView->QueryInterface(__uuidof(IShellView), (void **)&spsv)) &&
           SUCCEEDED(spsv->GetItemObject(SVGIO_BACKGROUND, __uuidof(IDispatch), (void **)&spdispView)) &&
           SUCCEEDED(spdispView->QueryInterface(__uuidof(IShellFolderViewDual),
                                                (void **)&spFolderView)) &&
           SUCCEEDED(spFolderView->get_Application(&spdispShell)) &&
           SUCCEEDED(spdispShell->QueryInterface(__uuidof(IShellDispatch2), (void **)&dispatcher)))
        {
          VARIANT show = {};
          show.vt = VT_I4;
          show.lVal = SW_SHOWNORMAL;

          std::wstring qdhr = wide_path + L"/qdhr.exe";

          BSTR path = SysAllocStringLen(qdhr.c_str(), (UINT)qdhr.size());
          memcpy(path, qdhr.c_str(), qdhr.size());

          VARIANT param = {};
          param.vt = VT_BSTR;
          param.bstrVal = SysAllocString(L"--updatedone");

          // return value unclear, we just assume if we got this far that it works.
          dispatcher->ShellExecute(path, param, empty, empty, show);

          SysFreeString(param.bstrVal);
          SysFreeString(path);

          return 0;
        }
      }
    }

    // if the de-elevation failed, we will just launch as admin

    cmdline = L"\"";
    cmdline += wide_path;
    cmdline += L"/qdhr.exe\" --updatedone";
    ZeroMemory(paramsAlloc, sizeof(wchar_t) * 512);
    wcscpy_s(paramsAlloc, 511, cmdline.c_str());

    ZeroMemory(&pi, sizeof(pi));
    ZeroMemory(&si, sizeof(si));

    CreateProcessW(NULL, paramsAlloc, NULL, NULL, FALSE, 0, NULL, NULL, &si, &pi);

    if(pi.dwProcessId != 0)
    {
      CloseHandle(pi.hProcess);
      CloseHandle(pi.hThread);
    }

    delete[] paramsAlloc;

    return 0;
  }
};

#if CRASH_HANDLER
struct CrashHandlerCommand : public Command
{
private:
  std::wstring pipe;

public:
  CrashHandlerCommand() {}
  virtual void AddOptions(cmdline::parser &parser) { parser.add<std::string>("pipe", 0, ""); }
  virtual const char *Description() { return "Internal use only!"; }
  virtual bool IsInternalOnly() { return true; }
  virtual bool IsCaptureCommand() { return false; }
  virtual bool Parse(cmdline::parser &parser, GlobalEnvironment &)
  {
    pipe = conv(parser.get<std::string>("pipe"));
    return true;
  }
  virtual rdcarray<rdcstr> ReplayArgs() { return {"--crash"}; }
  virtual int Execute(const CaptureOptions &)
  {
    CrashGenerationServer *crashServer = NULL;

    wchar_t tempPath[MAX_PATH] = {0};
    GetTempPathW(MAX_PATH - 1, tempPath);

    std::wstring dumpFolder = tempPath;

    // create each parent directory separately, and use \\s

    dumpFolder += L"DHR";
    CreateDirectoryW(dumpFolder.c_str(), NULL);

    dumpFolder += L"\\dumps";
    CreateDirectoryW(dumpFolder.c_str(), NULL);

    crashServer =
        new CrashGenerationServer(pipe.c_str(), NULL, OnClientConnected, NULL, OnClientCrashed,
                                  NULL, OnClientExited, NULL, NULL, NULL, true, &dumpFolder);

    if(!crashServer->Start())
    {
      delete crashServer;
      crashServer = NULL;
      return 1;
    }

    HANDLE readyEvent = CreateEventA(NULL, TRUE, FALSE, "DHR_CRASHHANDLE");

    if(readyEvent != NULL)
    {
      SetEvent(readyEvent);

      CloseHandle(readyEvent);
    }

    const int loopSleep = 100;
    int elapsedTime = 0;

    MSG msg;
    ZeroMemory(&msg, sizeof(msg));
    while(!exitServer)
    {
      // Check to see if any messages are waiting in the queue
      while(PeekMessage(&msg, NULL, 0, 0, PM_REMOVE))
      {
        // Translate the message and dispatch it to WindowProc()
        TranslateMessage(&msg);
        DispatchMessage(&msg);
      }

      // If the message is WM_QUIT, exit the while loop
      if(msg.message == WM_QUIT)
        break;

      Sleep(loopSleep);
      elapsedTime += loopSleep;

      // break out of the loop if
      if(elapsedTime > 5000 && !clientConnected)
        break;
    }

    delete crashServer;
    crashServer = NULL;

    std::wstring wlogpath;

    if(!wdump.empty())
    {
      std::string report = "{\n";

      for(size_t i = 0; i < customInfo.size(); i++)
      {
        std::wstring name = customInfo[i].name;
        std::wstring val = customInfo[i].value;

        if(name == L"logpath")
        {
          wlogpath = val;
        }
        else if(name == L"ptime")
        {
          // breakpad uptime, ignore.
        }
        else
        {
          report += "  \"" + conv(name) + "\": \"" + conv(val) + "\",\n";
        }
      }

      FILETIME filetime = {};
      SYSTEMTIME systime = {};
      GetSystemTimeAsFileTime(&filetime);
      FileTimeToSystemTime(&filetime, &systime);

      uint32_t milliseconds = 0;
      milliseconds += systime.wHour;
      milliseconds *= 60;
      milliseconds += systime.wMinute;
      milliseconds *= 60;
      milliseconds += systime.wSecond;
      milliseconds *= 1000;
      milliseconds += systime.wMilliseconds;

      std::string dumpId;

      char base62[63] = "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ";
      while(milliseconds > 0)
      {
        char c = base62[milliseconds % 63];
        dumpId.push_back(base62[milliseconds % 62]);
        milliseconds /= 62;
      }

      std::string reportPath = conv(dumpFolder) + "\\" + dumpId + ".zip";

      DHR_CreateBugReport(rdcstr(conv(wlogpath).c_str()), rdcstr(conv(wdump).c_str()),
                          rdcstr(reportPath.c_str()));

      for(size_t i = 0; i < reportPath.size(); i++)
        if(reportPath[i] == '\\')
          reportPath[i] = '/';

      report += "  \n\"report\": \"" + reportPath + "\"\n";
      report += "}\n";

      {
        std::wstring destjson = dumpFolder + L"\\" + conv(dumpId) + L".json";

        FILE *f = NULL;
        _wfopen_s(&f, destjson.c_str(), L"w");
        if(!f)
        {
          OutputDebugStringA("Coudln't open report json");
        }
        else
        {
          fputs(report.c_str(), f);
          fclose(f);

          wchar_t *paramsAlloc = new wchar_t[512];

          ZeroMemory(paramsAlloc, sizeof(wchar_t) * 512);

          GetModuleFileNameW(NULL, paramsAlloc, 511);

          wchar_t *lastSlash = wcsrchr(paramsAlloc, '\\');

          if(lastSlash)
            *lastSlash = 0;

          std::wstring exepath = paramsAlloc;

          ZeroMemory(paramsAlloc, sizeof(wchar_t) * 512);

          _snwprintf_s(paramsAlloc, 511, 511, L"%s/qdhr.exe --crash %s", exepath.c_str(),
                       destjson.c_str());

          PROCESS_INFORMATION pi;
          STARTUPINFOW si;
          ZeroMemory(&pi, sizeof(pi));
          ZeroMemory(&si, sizeof(si));

          BOOL success = CreateProcessW(NULL, paramsAlloc, NULL, NULL, FALSE, 0, NULL,
                                        exepath.c_str(), &si, &pi);

          if(success && pi.hProcess)
          {
            WaitForSingleObject(pi.hProcess, INFINITE);
          }

          if(pi.hProcess)
            CloseHandle(pi.hProcess);
          if(pi.hThread)
            CloseHandle(pi.hThread);

          std::wstring wreport = conv(reportPath);

          DeleteFileW(wreport.c_str());
          DeleteFileW(destjson.c_str());
        }
      }
    }

    if(!wdump.empty())
      DeleteFileW(wdump.c_str());

    if(!wlogpath.empty())
      DeleteFileW(wlogpath.c_str());

    return 0;
  }
};
#endif

struct GlobalHookCommand : public Command
{
private:
  std::wstring wpathmatch;
  std::string capfile;
  std::string debuglog;
  std::string opts;

public:
  GlobalHookCommand() {}
  virtual void AddOptions(cmdline::parser &parser)
  {
    parser.add<std::string>("match", 0, "");
    parser.add<std::string>("capfile", 0, "");
    parser.add<std::string>("debuglog", 0, "");
    parser.add<std::string>("capopts", 0, "");
  }
  virtual const char *Description() { return "Internal use only!"; }
  virtual bool IsInternalOnly() { return true; }
  virtual bool IsCaptureCommand() { return false; }
  virtual bool Parse(cmdline::parser &parser, GlobalEnvironment &)
  {
    wpathmatch = conv(parser.get<std::string>("match"));
    capfile = parser.get<std::string>("capfile");
    debuglog = parser.get<std::string>("debuglog");
    opts = parser.get<std::string>("capopts");
    return true;
  }
  virtual int Execute(const CaptureOptions &)
  {
    CaptureOptions cmdopts;
    cmdopts.DecodeFromString(rdcstr(opts.c_str(), opts.size()));

    // make sure the user doesn't accidentally run this with 'a' as a parameter or something.
    // "a.exe" is over 4 characters so this limit should not be a problem.
    if(wpathmatch.length() < 4)
    {
      std::cerr
          << "globalhook path match is too short/general. Danger of matching too many processes!"
          << std::endl;
      return 1;
    }

    wchar_t rdocpath[1024];

    // fetch path to our matching dhr.dll
    HMODULE rdoc = GetModuleHandleA("dhr.dll");

    if(rdoc == NULL)
    {
      std::cerr << "globalhook couldn't find dhr.dll!" << std::endl;
      return 1;
    }

    GetModuleFileNameW(rdoc, rdocpath, _countof(rdocpath) - 1);
    FreeLibrary(rdoc);

    // Create stdin pipe from parent program, to stay open until requested to close
    HANDLE pipe = GetStdHandle(STD_INPUT_HANDLE);

    if(pipe == INVALID_HANDLE_VALUE)
    {
      std::cerr << "globalhook couldn't open stdin pipe.\n" << std::endl;
      return 1;
    }

    HANDLE datahandle = OpenFileMappingA(FILE_MAP_READ, FALSE, GLOBAL_HOOK_DATA_NAME);

    if(datahandle != NULL)
    {
      CloseHandle(pipe);
      CloseHandle(datahandle);
      std::cerr << "globalhook found pre-existing global data, not creating second global hook."
                << std::endl;
      return 1;
    }

    datahandle = CreateFileMappingA(INVALID_HANDLE_VALUE, NULL, PAGE_READWRITE, 0, sizeof(ShimData),
                                    GLOBAL_HOOK_DATA_NAME);

    if(datahandle)
    {
      ShimData *shimdata = (ShimData *)MapViewOfFile(datahandle, FILE_MAP_WRITE | FILE_MAP_READ, 0,
                                                     0, sizeof(ShimData));

      if(shimdata)
      {
        memset(shimdata, 0, sizeof(ShimData));

        wcsncpy_s(shimdata->pathmatchstring, wpathmatch.c_str(), _TRUNCATE);
        wcsncpy_s(shimdata->rdocpath, rdocpath, _TRUNCATE);
        strncpy_s(shimdata->capfile, capfile.c_str(), _TRUNCATE);
        strncpy_s(shimdata->debuglog, debuglog.c_str(), _TRUNCATE);
        memcpy(shimdata->opts, &cmdopts, sizeof(CaptureOptions));

        static_assert(sizeof(CaptureOptions) <= sizeof(shimdata->opts),
                      "ShimData options is too small");

        // wait until a write comes in over the pipe
        char buf[16] = {0};
        DWORD read = 0;
        ReadFile(pipe, buf, sizeof(buf), &read, NULL);

        UnmapViewOfFile(shimdata);
      }
      else
      {
        std::cerr << "globalhook couldn't map global data store." << std::endl;
      }

      CloseHandle(datahandle);
    }
    else
    {
      std::cerr << "globalhook couldn't create global data store." << std::endl;
    }

    CloseHandle(pipe);

    return 0;
  }
};

static BOOL WINAPI WatchCtrlHandler(DWORD type)
{
  if(type == CTRL_C_EVENT || type == CTRL_BREAK_EVENT || type == CTRL_CLOSE_EVENT)
  {
    killSignal = true;
    return TRUE;
  }

  return FALSE;
}

namespace
{
struct WatchProcEntry
{
  uint32_t pid = 0;
  uint32_t ppid = 0;
  std::wstring name;
};

// maps an --api name (already lower-cased) to the DLL whose presence in a child marks it as using
// that graphics API. "any" returns an empty string, meaning no filter, and an unrecognised name
// returns NULL so the caller can reject it.
const wchar_t *ApiMarkerDll(const std::string &api)
{
  if(api == "vulkan")
    return L"vulkan-1.dll";
  if(api == "d3d12")
    return L"d3d12.dll";
  if(api == "d3d11")
    return L"d3d11.dll";
  if(api == "d3d9")
    return L"d3d9.dll";
  if(api == "opengl")
    return L"opengl32.dll";
  if(api == "any")
    return L"";

  return NULL;
}

// case-insensitive substring test, matching the semantics dhrshim uses for its path match
bool ContainsInsensitive(const std::wstring &haystack, const std::wstring &needle)
{
  if(needle.empty())
    return true;

  std::wstring h = haystack;
  std::wstring n = needle;

  std::transform(h.begin(), h.end(), h.begin(), towlower);
  std::transform(n.begin(), n.end(), n.begin(), towlower);

  return h.find(n) != std::wstring::npos;
}

// true if the given process is 32-bit running under a 64-bit OS
bool IsTarget32Bit(uint32_t pid)
{
  HANDLE h = OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, FALSE, pid);

  if(h == NULL)
    return false;

  BOOL wow64 = FALSE;
  BOOL ok = IsWow64Process(h, &wow64);

  CloseHandle(h);

  return ok && wow64;
}

// prints any process mitigation policies that are enabled on the target. This is the native
// equivalent of `Get-ProcessMitigation -Id <pid>`, checked at injection time because a binary
// signature or image load policy is enough on its own to make the loader refuse to map our
// unsigned dhr.dll into the process.
void ReportMitigations(uint32_t pid)
{
  // PROCESS_QUERY_INFORMATION is the minimum needed, and is unrelated to what injection needs
  HANDLE h = OpenProcess(PROCESS_QUERY_INFORMATION, FALSE, pid);

  if(h == NULL)
  {
    std::cerr << "  Mitigations: couldn't query (OpenProcess error " << GetLastError() << ")"
              << std::endl;
    return;
  }

  bool any = false;

  PROCESS_MITIGATION_BINARY_SIGNATURE_POLICY signature = {};

  if(GetProcessMitigationPolicy(h, ProcessSignaturePolicy, &signature, sizeof(signature)) &&
     (signature.MicrosoftSignedOnly || signature.StoreSignedOnly))
  {
    any = true;
    std::cerr << "  Mitigation [BINARY SIGNATURE]: "
              << (signature.MicrosoftSignedOnly ? "MicrosoftSignedOnly" : "StoreSignedOnly")
              << "  <- blocks loading unsigned DLLs" << std::endl;
  }

  PROCESS_MITIGATION_IMAGE_LOAD_POLICY imageload = {};

  if(GetProcessMitigationPolicy(h, ProcessImageLoadPolicy, &imageload, sizeof(imageload)))
  {
    std::string flags;

    if(imageload.NoRemoteImages)
      flags += "NoRemoteImages ";
    if(imageload.NoLowMandatoryLabelImages)
      flags += "NoLowMandatoryLabelImages ";
    if(imageload.PreferSystem32Images)
      flags += "PreferSystem32Images ";
    if(imageload.AuditNoRemoteImages)
      flags += "AuditNoRemoteImages ";
    if(imageload.AuditNoLowMandatoryLabelImages)
      flags += "AuditNoLowMandatoryLabelImages ";

    if(!flags.empty())
    {
      any = true;
      std::cerr << "  Mitigation [IMAGE LOAD]: " << flags << std::endl;
    }
  }

  PROCESS_MITIGATION_DYNAMIC_CODE_POLICY dynamiccode = {};

  if(GetProcessMitigationPolicy(h, ProcessDynamicCodePolicy, &dynamiccode, sizeof(dynamiccode)) &&
     dynamiccode.ProhibitDynamicCode)
  {
    any = true;
    std::cerr << "  Mitigation [DYNAMIC CODE]: ProhibitDynamicCode" << std::endl;
  }

  PROCESS_MITIGATION_EXTENSION_POINT_DISABLE_POLICY extpoints = {};

  if(GetProcessMitigationPolicy(h, ProcessExtensionPointDisablePolicy, &extpoints, sizeof(extpoints)) &&
     extpoints.DisableExtensionPoints)
  {
    any = true;
    std::cerr << "  Mitigation [EXTENSION POINTS]: DisableExtensionPoints" << std::endl;
  }

  PROCESS_MITIGATION_STRICT_HANDLE_CHECK_POLICY handles = {};

  if(GetProcessMitigationPolicy(h, ProcessStrictHandleCheckPolicy, &handles, sizeof(handles)) &&
     handles.RaiseExceptionOnInvalidHandleReference)
  {
    any = true;
    std::cerr << "  Mitigation [STRICT HANDLES]: RaiseExceptionOnInvalidHandleReference" << std::endl;
  }

  PROCESS_MITIGATION_SYSTEM_CALL_DISABLE_POLICY syscalls = {};

  if(GetProcessMitigationPolicy(h, ProcessSystemCallDisablePolicy, &syscalls, sizeof(syscalls)) &&
     syscalls.DisallowWin32kSystemCalls)
  {
    any = true;
    std::cerr << "  Mitigation [SYSTEM CALLS]: DisallowWin32kSystemCalls" << std::endl;
  }

  if(!any)
    std::cout << "  Mitigations: none of the queryable policies are enabled." << std::endl;

  CloseHandle(h);
}

// reports the target's CRT/runtime modules that did NOT come from System32. dhr.dll imports
// MSVCP140/VCRUNTIME140, and the loader binds those imports against whatever copy of that module
// the process already has loaded. A target that ships its own older copies (very common for games)
// makes the load fail with ERROR_PROC_NOT_FOUND even though nothing is blocking us.
void ReportRuntimeModules(uint32_t pid)
{
  static const wchar_t *crtNames[] = {
      L"msvcp140.dll",
      L"msvcp140_1.dll",
      L"msvcp140_2.dll",
      L"msvcp140_codecvt_ids.dll",
      L"vcruntime140.dll",
      L"vcruntime140_1.dll",
      L"vcruntime140_threads.dll",
      L"ucrtbase.dll",
      L"concrt140.dll",
  };

  int found = 0;
  int foreign = 0;
  bool ok = false;
  DWORD lastErr = 0;

  // the module list can change while we're walking it, which comes back as ERROR_BAD_LENGTH -
  // retry the same way FindRemoteDLL does
  for(int attempt = 0; attempt < 10 && !ok; attempt++)
  {
    HANDLE snap = CreateToolhelp32Snapshot(TH32CS_SNAPMODULE, pid);

    if(snap == INVALID_HANDLE_VALUE)
    {
      lastErr = GetLastError();

      // ERROR_BAD_LENGTH: the list changed while we walked it. ERROR_PARTIAL_COPY: a module was
      // being loaded or unloaded underneath us. Both are transient, so retry.
      if(lastErr == ERROR_BAD_LENGTH || lastErr == ERROR_PARTIAL_COPY)
      {
        Sleep(5);
        continue;
      }

      break;
    }

    found = 0;
    foreign = 0;

    MODULEENTRY32W me = {};
    me.dwSize = sizeof(me);

    if(!Module32FirstW(snap, &me))
    {
      lastErr = GetLastError();

      CloseHandle(snap);

      // ERROR_BAD_LENGTH: the list changed while we walked it. ERROR_PARTIAL_COPY: a module was
      // being loaded or unloaded underneath us. Both are transient, so retry.
      if(lastErr == ERROR_BAD_LENGTH || lastErr == ERROR_PARTIAL_COPY)
      {
        Sleep(5);
        continue;
      }

      break;
    }

    ok = true;

    do
    {
      std::wstring name = me.szModule;
      std::transform(name.begin(), name.end(), name.begin(), towlower);

      bool crt = false;

      for(const wchar_t *n : crtNames)
      {
        if(name == n)
        {
          crt = true;
          break;
        }
      }

      if(!crt)
        continue;

      found++;

      std::wstring lower = me.szExePath;
      std::transform(lower.begin(), lower.end(), lower.begin(), towlower);

      const bool system32 = lower.find(L"\\windows\\system32\\") != std::wstring::npos ||
                            lower.find(L"\\windows\\syswow64\\") != std::wstring::npos;

      // only the non-System32 ones can clash with our imports
      if(system32)
        continue;

      foreign++;

      std::cerr << "  Runtime module NOT from System32: " << conv(me.szModule) << "  <- "
                << conv(me.szExePath) << std::endl;
    } while(Module32NextW(snap, &me));

    CloseHandle(snap);
  }

  if(!ok)
  {
    std::cerr << "  Runtime modules: couldn't enumerate the target's modules (error " << lastErr
              << ")." << std::endl;
    return;
  }

  if(found == 0)
    std::cout << "  Runtime modules: no CRT modules loaded in the target." << std::endl;
  else if(foreign == 0)
    std::cout << "  Runtime modules: " << found << " CRT module(s), all from System32." << std::endl;
  else
    std::cerr << "  ^ dhr.dll imports the same CRT - a mismatched copy already loaded here will "
                 "make the load fail with ERROR_PROC_NOT_FOUND."
              << std::endl;
}

// true if the named module (matched case-insensitively against just the filename, e.g.
// "vulkan-1.dll") is currently loaded in the given process. Uses the same module snapshot as
// ReportRuntimeModules, with the same retries on the transient list-changed errors.
bool IsModuleLoaded(uint32_t pid, const std::wstring &moduleName)
{
  std::wstring want = moduleName;
  std::transform(want.begin(), want.end(), want.begin(), towlower);

  for(int attempt = 0; attempt < 10; attempt++)
  {
    HANDLE snap = CreateToolhelp32Snapshot(TH32CS_SNAPMODULE, pid);

    if(snap == INVALID_HANDLE_VALUE)
    {
      DWORD err = GetLastError();

      // ERROR_BAD_LENGTH: the list changed while we walked it. ERROR_PARTIAL_COPY: a module was
      // being loaded or unloaded underneath us. Both are transient, so retry.
      if(err == ERROR_BAD_LENGTH || err == ERROR_PARTIAL_COPY)
      {
        Sleep(5);
        continue;
      }

      return false;
    }

    MODULEENTRY32W me = {};
    me.dwSize = sizeof(me);

    if(!Module32FirstW(snap, &me))
    {
      DWORD err = GetLastError();

      CloseHandle(snap);

      if(err == ERROR_BAD_LENGTH || err == ERROR_PARTIAL_COPY)
      {
        Sleep(5);
        continue;
      }

      return false;
    }

    bool found = false;

    do
    {
      std::wstring name = me.szModule;
      std::transform(name.begin(), name.end(), name.begin(), towlower);

      if(name == want)
      {
        found = true;
        break;
      }
    } while(Module32NextW(snap, &me));

    CloseHandle(snap);

    return found;
  }

  return false;
}

// true if the file exists on disk
bool FileExists(const std::string &path)
{
  return GetFileAttributesW(conv(path).c_str()) != INVALID_FILE_ATTRIBUTES;
}

// builds a default debug log path in the build output folder, i.e. next to dhrcmd.exe
std::string DefaultWatchLogPath()
{
  std::vector<wchar_t> exepath(2048, 0);

  if(GetModuleFileNameW(NULL, exepath.data(), (DWORD)exepath.size() - 1) == 0)
    return std::string();

  wchar_t *lastSlash = wcsrchr(exepath.data(), '\\');

  if(lastSlash == NULL)
    return std::string();

  *lastSlash = 0;

  SYSTEMTIME st;
  GetLocalTime(&st);

  wchar_t file[MAX_PATH] = {0};

  _snwprintf_s(file, _countof(file), _TRUNCATE, L"%s\\dhrwatch_%04d.%02d.%02d_%02d.%02d.%02d.log",
               exepath.data(), st.wYear, st.wMonth, st.wDay, st.wHour, st.wMinute, st.wSecond);

  return conv(std::wstring(file));
}

bool SnapshotProcesses(std::vector<WatchProcEntry> &out)
{
  out.clear();

  HANDLE snap = CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0);

  if(snap == INVALID_HANDLE_VALUE)
    return false;

  PROCESSENTRY32W pe = {};
  pe.dwSize = sizeof(pe);

  if(Process32FirstW(snap, &pe))
  {
    do
    {
      WatchProcEntry e;
      e.pid = pe.th32ProcessID;
      e.ppid = pe.th32ParentProcessID;
      e.name = pe.szExeFile;
      out.push_back(e);
    } while(Process32NextW(snap, &pe));
  }

  CloseHandle(snap);

  return true;
}

// Windows' Sleep() rounds up to the ~15ms system tick unless the timer resolution is raised, so
// for short intervals sleep the bulk of the time and spin out the tail. This is what makes a 1ms
// poll interval actually mean ~1ms.
void PreciseSleep(uint32_t ms)
{
  if(ms > 2)
  {
    Sleep(ms - 1);
    ms = 1;
  }

  LARGE_INTEGER freq, start, now;
  QueryPerformanceFrequency(&freq);
  QueryPerformanceCounter(&start);

  const double target = (double)ms / 1000.0;

  do
  {
    QueryPerformanceCounter(&now);
  } while((double)(now.QuadPart - start.QuadPart) / (double)freq.QuadPart < target);
}

// Draws the live process tree plus its summary line as one block that refreshes in place: the
// cursor is moved back over the previous block before redrawing, so the console line count never
// grows. When stdout isn't a console there is no cursor to move, so the block is just appended.
struct WatchTreeDisplay
{
  size_t lines = 0;    // rows the last drawn block occupies
  size_t width = 0;    // widest row seen, so shorter rows still blank out the old text

  void Init() {}
  void Shutdown() { Clear(); }

  // wipes the block so a permanent message can be printed on clean lines
  void Clear()
  {
    HANDLE h = GetStdHandle(STD_OUTPUT_HANDLE);
    CONSOLE_SCREEN_BUFFER_INFO info;

    if(lines && GetConsoleScreenBufferInfo(h, &info))
    {
      COORD p = info.dwCursorPosition;
      p.Y = (SHORT)(p.Y - (SHORT)lines);
      SetConsoleCursorPosition(h, p);

      for(size_t i = 0; i < lines; i++)
        std::cout << std::string(width, ' ') << '\n';

      SetConsoleCursorPosition(h, p);
    }

    lines = 0;
    std::cout << std::flush;
  }

  void Draw(const std::vector<std::string> &block)
  {
    HANDLE h = GetStdHandle(STD_OUTPUT_HANDLE);
    CONSOLE_SCREEN_BUFFER_INFO info;
    const bool console = GetConsoleScreenBufferInfo(h, &info) != 0;

    if(console && lines)
    {
      COORD p = info.dwCursorPosition;
      p.Y = (SHORT)(p.Y - (SHORT)lines);
      SetConsoleCursorPosition(h, p);
    }

    for(const std::string &l : block)
      width = width > l.size() ? width : l.size();

    for(const std::string &l : block)
    {
      std::cout << l;

      if(console)
        std::cout << std::string(width - l.size(), ' ');

      std::cout << '\n';
    }

    lines = block.size();
    std::cout << std::flush;
  }
};
// builds the indented process tree under rootPid from a process snapshot, e.g.
//
//   launcher.exe (1234)
//      child.exe (5678)
//
// Siblings are listed in ascending pid order. Each pid is visited at most once and the depth is
// capped, so a broken, recycled or looping parent chain can't make the walk run away, and a
// process whose parent chain doesn't reach rootPid never appears. Returns the number of non-root
// processes shown.
size_t BuildProcessTree(uint32_t rootPid, const std::string &rootFallbackName,
                        const std::vector<WatchProcEntry> &procs, std::vector<std::string> &out)
{
  const int maxDepth = 16;

  out.clear();

  // index every process by parent, sorted by pid within each parent
  std::vector<const WatchProcEntry *> byParent;
  byParent.reserve(procs.size());

  const WatchProcEntry *root = NULL;

  for(const WatchProcEntry &e : procs)
  {
    if(e.pid == rootPid)
      root = &e;

    byParent.push_back(&e);
  }

  std::sort(byParent.begin(), byParent.end(), [](const WatchProcEntry *a, const WatchProcEntry *b) {
    if(a->ppid != b->ppid)
      return a->ppid < b->ppid;

    return a->pid < b->pid;
  });

  std::string rootName = root ? conv(root->name) : rootFallbackName;

  if(rootName.empty())
    rootName = "pid " + std::to_string(rootPid);

  out.push_back("  " + rootName + " (" + std::to_string(rootPid) + ")" + (root ? "" : " (exited)"));

  // if the watched process is gone the tree is just its (exited) root - don't walk, children may
  // have been reparented or left orphaned under a stale parent id
  if(!root)
    return 0;

  struct Item
  {
    const WatchProcEntry *entry;
    int depth;
  };

  std::vector<Item> stack;
  std::set<uint32_t> visited;
  visited.insert(rootPid);

  auto pushChildren = [&](uint32_t parent, int childDepth) {
    if(childDepth > maxDepth)
      return;

    // the direct children of this parent, in ascending pid order
    auto first = std::lower_bound(byParent.begin(), byParent.end(), parent,
                                  [](const WatchProcEntry *a, uint32_t p) { return a->ppid < p; });
    auto last = std::upper_bound(first, byParent.end(), parent,
                                 [](uint32_t p, const WatchProcEntry *a) { return p < a->ppid; });

    // pushed in reverse so they pop in ascending pid order
    for(auto it = last; it != first;)
    {
      --it;

      if(visited.count((*it)->pid) == 0)
        stack.push_back({*it, childDepth});
    }
  };

  pushChildren(rootPid, 1);

  size_t count = 0;

  while(!stack.empty())
  {
    Item item = stack.back();
    stack.pop_back();

    // never render the same pid twice, so a cycle or a reused pid can't loop forever
    if(!visited.insert(item.entry->pid).second)
      continue;

    out.push_back(std::string((size_t)(2 + 3 * item.depth), ' ') + conv(item.entry->name) + " (" +
                  std::to_string(item.entry->pid) + ")");
    count++;

    pushChildren(item.entry->pid, item.depth + 1);
  }

  return count;
}

// strips any directory components from a path
std::string Basename(const std::string &path)
{
  size_t pos = path.find_last_of("\\/");

  return pos == std::string::npos ? path : path.substr(pos + 1);
}

// the env var DHR sets to turn on its Vulkan layer. This is DHR_VULKAN_LAYER_VAR from
// dhr/common/globalconfig.h, and is exactly what DHR's own in-process child hooking
// (dhr/os/win32/sys_win32_hooks.cpp) sets for the children it spawns. The literal is repeated here
// because dhrcmd doesn't include DHR's internal headers.
static const wchar_t *kVulkanLayerEnv = L"ENABLE_VULKAN_DHR_CAPTURE=1";
static const wchar_t *kVulkanLayerEnvPrefix = L"ENABLE_VULKAN_DHR_CAPTURE=";

// case-insensitive check that an environment entry begins with the given "NAME=" prefix
bool EnvEntryHasPrefix(const wchar_t *entry, const wchar_t *prefix)
{
  while(*prefix)
  {
    if(*entry == 0 || towlower(*entry) != towlower(*prefix))
      return false;

    entry++;
    prefix++;
  }

  return true;
}

// launches a program with the given arguments, returning its pid
bool LaunchProcessWithArgs(uint32_t &pid, const std::string &exe,
                           const std::vector<std::string> &args, const std::string &workingDir)
{
  std::wstring cmdline = L"\"";
  cmdline += conv(exe);
  cmdline += L"\"";

  for(const std::string &a : args)
  {
    cmdline += L" ";
    cmdline += conv(a);
  }

  // build a copy of our environment with the Vulkan layer enabled, so every descendant of the
  // launched tree inherits it. This matches what DHR's own child hooking does; without it the
  // layer never loads in the child and no Vulkan capture is possible. Win32 walks this as a
  // double-NUL-terminated block of L"KEY=VALUE" strings.
  std::vector<wchar_t> env;
  {
    LPWCH original = GetEnvironmentStringsW();

    if(original)
    {
      for(LPWCH p = original; *p; p += wcslen(p) + 1)
      {
        // drop any existing copy of the variable so ours below wins
        if(EnvEntryHasPrefix(p, kVulkanLayerEnvPrefix))
          continue;

        env.insert(env.end(), p, p + wcslen(p) + 1);
      }

      FreeEnvironmentStringsW(original);
    }

    env.insert(env.end(), kVulkanLayerEnv, kVulkanLayerEnv + wcslen(kVulkanLayerEnv) + 1);

    // terminator for the whole block
    env.push_back(0);
  }

  std::wstring wdir = conv(workingDir);

  STARTUPINFOW si;
  PROCESS_INFORMATION pi;
  ZeroMemory(&si, sizeof(si));
  ZeroMemory(&pi, sizeof(pi));
  si.cb = sizeof(si);

  // the environment block is Unicode, so CreateProcessW must be told so
  if(!CreateProcessW(NULL, &cmdline[0], NULL, NULL, FALSE, CREATE_UNICODE_ENVIRONMENT, env.data(),
                     wdir.empty() ? NULL : wdir.c_str(), &si, &pi))
    return false;

  pid = pi.dwProcessId;

  CloseHandle(pi.hThread);
  CloseHandle(pi.hProcess);

  return true;
}
}    // namespace

// Watches an existing process and injects DHR into any child process it starts. Unlike the
// hookIntoChildren capture option this doesn't require DHR to be loaded into the process being
// watched, but it does mean we can only see children once they already exist - there is an
// inherent race if a child initialises its graphics API faster than we can poll for it.
struct WatchCommand : public Command
{
private:
  std::string executable;
  std::vector<std::string> programArgs;
  uint32_t targetPID = 0;
  std::string workingDir;
  std::string childFilter;
  uint32_t pollMS = 1;
  bool launchGUI = true;
  std::string captureFile;
  std::string debugLogFile;
  bool waitForExit = false;

  // the lower-cased --api name, for messages, and the DLL whose presence in a child marks it as
  // using that API. An empty apiMarkerDll means "any" - no filtering at all.
  std::string apiName = "any";
  std::wstring apiMarkerDll;

  // how long a child may take to load apiMarkerDll before we give up on it
  uint32_t apiWaitMS = 10000;

  // owns the live in-place process tree drawn below the header
  WatchTreeDisplay display;

public:
  WatchCommand() : Command() {}

  virtual void AddOptions(cmdline::parser &parser)
  {
    parser.set_footer("<executable> [program arguments]");
    parser.stop_at_rest(true);

    parser.add<uint32_t>("pid", 0,
                         "Watch this already-running process instead of launching one. Give it "
                         "either an executable to launch or a --pid, not both.",
                         false, 0);
    parser.add<std::string>("child", 0,
                            "If given, only child processes whose executable name contains this "
                            "substring (case-insensitive) are injected.",
                            false);
    parser.add<std::string>("api", 0,
                            "Only inject children that use this graphics API, one of: vulkan, "
                            "d3d12, d3d11, d3d9, opengl, any. A child is deferred until it loads "
                            "the API's DLL, up to --api-wait. Default is any, which injects "
                            "immediately as before.",
                            false, "any");
    parser.add<uint32_t>(
        "api-wait", 0,
        "How long to keep waiting for a child to load its API's DLL (see --api) before skipping "
        "it, in milliseconds.",
        false, 10000, cmdline::range(0, 60000));
    parser.add<uint32_t>("poll-ms", 0, "How often to poll for new child processes, in milliseconds.",
                         false, 1, cmdline::range(1, 60000));
    parser.add("no-gui", 0,
               "Don't open the GUI. By default the interface is launched connected to each "
               "injected child process.");
    parser.add<std::string>("debuglog", 0,
                            "Write DHR's debug log to this file. The injected processes share the "
                            "same log, so startup and injection problems are recorded there. "
                            "Default is a timestamped file next to dhrcmd.exe.",
                            false);
  }

  virtual const char *Description()
  {
    return "Watches a process and injects DHR into any child processes it starts.";
  }

  virtual bool IsInternalOnly() { return false; }
  virtual bool IsCaptureCommand() { return true; }

  virtual bool Parse(cmdline::parser &parser, GlobalEnvironment &)
  {
    targetPID = parser.get<uint32_t>("pid");
    childFilter = parser.get<std::string>("child");
    pollMS = parser.get<uint32_t>("poll-ms");
    launchGUI = !parser.exist("no-gui");
    captureFile = parser.get<std::string>("capture-file");
    debugLogFile = parser.get<std::string>("debuglog");
    workingDir = parser.get<std::string>("working-dir");
    waitForExit = parser.exist("wait-for-exit");

    apiName = parser.get<std::string>("api");
    std::transform(apiName.begin(), apiName.end(), apiName.begin(), ::tolower);
    apiWaitMS = parser.get<uint32_t>("api-wait");

    const wchar_t *marker = ApiMarkerDll(apiName);

    if(marker == NULL)
    {
      std::cerr << "Error: unknown --api '" << apiName
                << "'. Valid values are: vulkan, d3d12, d3d11, d3d9, opengl, any." << std::endl
                << std::endl
                << parser.usage();
      return false;
    }

    apiMarkerDll = marker;

    std::vector<std::string> rest = parser.rest();
    parser.set_rest({});

    if(targetPID != 0 && !rest.empty())
    {
      std::cerr << "Error: give either an executable to launch or a --pid, not both." << std::endl
                << std::endl
                << parser.usage();
      return false;
    }

    if(targetPID == 0 && rest.empty())
    {
      std::cerr << "Error: give an executable to launch, or --pid of a running process." << std::endl
                << std::endl
                << parser.usage();
      return false;
    }

    if(!rest.empty())
    {
      executable = rest[0];
      programArgs.assign(rest.begin() + 1, rest.end());
    }

    return true;
  }

  virtual int Execute(const CaptureOptions &opts)
  {
    SetConsoleCtrlHandler(&WatchCtrlHandler, TRUE);

    // set up a debug log, so that if an injection or capture fails we have something to look at
    // afterwards. Injected processes inherit this same log, so anything they report during their
    // own startup lands here too.
    const std::string logPath = debugLogFile.empty() ? DefaultWatchLogPath() : debugLogFile;

    if(!logPath.empty())
    {
      DHR_SetDebugLogFile(rdcstr(logPath.c_str(), logPath.size()));

      std::cout << "Debug log: " << logPath << std::endl;

      if(!FileExists(logPath))
        std::cerr << "Warning: DHR did not create the debug log at " << logPath << std::endl;
    }

    const std::wstring wchild = conv(childFilter);

    const rdcstr captureTemplate(captureFile.c_str(), captureFile.size());

    std::vector<WatchProcEntry> procs;

    uint32_t pid = 0;
    bool attachToExisting = false;

    if(!executable.empty())
    {
      if(!LaunchProcessWithArgs(pid, executable, programArgs, workingDir))
      {
        std::cerr << "Failed to launch '" << executable << "' (error " << GetLastError() << ")."
                  << std::endl;
        return 1;
      }
    }
    else
    {
      pid = targetPID;
      attachToExisting = true;
    }

    const uint64_t start = GetTickCount64();

    const std::string label =
        !executable.empty() ? Basename(executable) : std::string("pid ") + std::to_string(pid);

    // set up the in-place tree display
    display.Init();

    if(attachToExisting)
      std::cout << "Watching PID " << pid << " (" << label << ")";
    else
      std::cout << "Launched '" << executable << "' (PID " << pid << ")";

    std::cout << ", polling every " << pollMS << "ms for child processes";

    if(!childFilter.empty())
      std::cout << " matching '" << childFilter << "'";

    if(apiName != "any")
      std::cout << ", only injecting children that load the " << apiName << " API";

    std::cout << ". Press Ctrl-C to stop." << std::endl;

    std::cout << std::endl;

    // a process that was already running when we attached had its environment fixed at creation
    // time, so we can't retroactively enable the Vulkan layer for it - the layer has to be present
    // when the Vulkan instance is created. Vulkan capture in its tree may therefore not work.
    if(attachToExisting)
      std::cerr << "Warning: --pid attaches to a process that started before watch, so the Vulkan "
                   "layer cannot be enabled for it and Vulkan capture may not work."
                << std::endl;

    std::set<uint32_t> seen;
    size_t seenCount = 0;
    size_t injectedCount = 0;

    // children that matched the filter but hadn't loaded their API's DLL yet. Each is re-checked
    // every poll and injected as soon as the DLL appears, or dropped once its deadline passes.
    struct PendingChild
    {
      uint32_t pid;
      std::wstring name;
      uint64_t deadline;
    };
    std::vector<PendingChild> pending;

    // when we launched the parent ourselves, everything it spawns is a legitimate child so no
    // baseline is needed. When attaching to a process that's already running, ignore whatever
    // already exists before we started watching.
    if(attachToExisting && SnapshotProcesses(procs))
    {
      for(const WatchProcEntry &e : procs)
        seen.insert(e.pid);
    }

    seen.insert(pid);

    uint64_t lastDraw = 0;

    // the tree lines from the last redraw, so we know when the tree has actually changed. The
    // name used for the root if the watched process itself is no longer in the snapshot
    std::vector<std::string> treeLines;
    std::vector<std::string> lastTreeLines;
    const std::string treeRootName = Basename(executable);

    while(!killSignal)
    {
      PreciseSleep(pollMS);

      const uint64_t now = GetTickCount64();

      if(SnapshotProcesses(procs))
      {
        for(const WatchProcEntry &e : procs)
        {
          if(e.pid == 0 || e.ppid != pid)
            continue;

          if(seen.count(e.pid))
            continue;

          // "seen" counts every distinct direct child we spot, whether or not it matches the
          // filter or ends up injected. A child deferred waiting for its API is counted here once,
          // when first seen, and kept in the pending list below.
          seen.insert(e.pid);
          seenCount++;

          if(!ContainsInsensitive(e.name, wchild))
            continue;

          // don't inject into our own tools, that would only recurse or be pointless
          if(ContainsInsensitive(e.name, L"dhrcmd.exe") || ContainsInsensitive(e.name, L"qdhr.exe"))
            continue;

          // a launcher's rendering child often initialises its graphics API a moment after it
          // starts, so if the requested API's DLL isn't loaded yet wait for it rather than giving
          // up. An empty apiMarkerDll means "any", so we never defer in that case.
          if(!apiMarkerDll.empty() && !IsModuleLoaded(e.pid, apiMarkerDll))
          {
            display.Clear();
            std::cout << std::endl;
            std::cout << "Child process " << conv(e.name) << " (PID " << e.pid
                      << ") has not loaded " << conv(apiMarkerDll) << " yet, waiting up to "
                      << apiWaitMS << "ms for it." << std::endl;
            std::cout << std::endl;

            pending.push_back({e.pid, e.name, now + apiWaitMS});
            continue;
          }

          if(InjectChildProcess(e.pid, e.name, logPath, captureTemplate, opts))
            injectedCount++;
        }
      }

      // re-check the children we deferred waiting for their API's DLL. Inject as soon as it shows
      // up, or drop and report once the deadline passes.
      for(size_t i = 0; i < pending.size();)
      {
        const PendingChild &p = pending[i];

        if(IsModuleLoaded(p.pid, apiMarkerDll))
        {
          if(InjectChildProcess(p.pid, p.name, logPath, captureTemplate, opts))
            injectedCount++;

          pending.erase(pending.begin() + i);
          continue;
        }

        if(now >= p.deadline)
        {
          display.Clear();
          std::cout << std::endl;
          std::cout << "Skipping child process " << conv(p.name) << " (PID " << p.pid
                    << "): it never loaded " << conv(apiMarkerDll) << " within " << apiWaitMS
                    << "ms of being seen." << std::endl;
          std::cout << std::endl;

          pending.erase(pending.begin() + i);
          continue;
        }

        i++;
      }

      // rebuild the tree every poll so we notice spawns promptly, but only redraw on a change or
      // once a second - redrawing at the poll rate would just flicker
      const size_t treeCount = BuildProcessTree(pid, treeRootName, procs, treeLines);

      const bool changed = (treeLines != lastTreeLines);

      if((changed && now - lastDraw >= 100) || now - lastDraw >= 1000)
      {
        lastDraw = now;

        // the summary is the last line of the block, so it redraws together with the tree as one
        // unit and never adds a line of its own
        std::vector<std::string> block = treeLines;

        block.push_back("[" + std::to_string((now - start) / 1000) + "s] PID " + std::to_string(pid) +
                        " | " + std::to_string(treeCount) + " child processes | seen " +
                        std::to_string(seenCount) + ", injected " + std::to_string(injectedCount));

        display.Draw(block);

        lastTreeLines = treeLines;
      }
    }

    // wipe the tree block so the farewell message lands on a clean line
    display.Shutdown();

    SetConsoleCtrlHandler(&WatchCtrlHandler, FALSE);

    std::cout << "Stopped watching." << std::endl;

    return 0;
  }

private:
  // prints the diagnostics for a child we've decided to inject and runs the injection itself.
  // returns true if the injection succeeded, so the caller knows whether to count it.
  bool InjectChildProcess(uint32_t childPid, const std::wstring &childName,
                          const std::string &logPath, const rdcstr &captureTemplate,
                          const CaptureOptions &opts)
  {
    const bool child32 = IsTarget32Bit(childPid);

    // wipe the live tree first so this message isn't interleaved with it
    display.Clear();
    std::cout << std::endl;
    std::cout << "Detected child process " << conv(childName) << " (PID " << childPid
              << (child32 ? ", 32-bit" : ", 64-bit") << "), injecting." << std::endl;
    std::cout << std::endl;

    ReportMitigations(childPid);
    ReportRuntimeModules(childPid);
    std::cout << std::endl;

    if(child32)
      std::cerr << "  Warning: 32-bit target. Injecting needs a matching 32-bit DHR build "
                   "(x86\\dhr.dll next to dhrcmd.exe, or a Win32\\<Config>\\ tree)."
                << std::endl;

    ExecuteResult res = DHR_InjectIntoProcess(childPid, rdcarray<EnvironmentModification>(),
                                              captureTemplate, opts, waitForExit);

    if(res.result.code != ResultCode::Succeeded)
    {
      std::cerr << "  Injection failed (code " << (uint32_t)res.result.code
                << "): " << res.result.Message().c_str() << std::endl;

      if(!logPath.empty())
      {
        if(FileExists(logPath))
          std::cerr << "  See the debug log for details: " << logPath << std::endl;
        else
          std::cerr << "  (no debug log was written - " << logPath << " doesn't exist)" << std::endl;
      }

      std::cout << std::endl;

      return false;
    }

    std::cout << "  Injected successfully (target control ident " << res.ident << ")." << std::endl;

    if(launchGUI)
      LaunchGUI(res.ident);

    std::cout << std::endl;

    return true;
  }

  static void LaunchGUI(uint32_t ident)
  {
    // qdhr.exe sits alongside dhrcmd.exe in the output directory
    std::vector<wchar_t> exepath(2048, 0);

    if(GetModuleFileNameW(NULL, exepath.data(), (DWORD)exepath.size() - 1) == 0)
    {
      std::cerr << "  Couldn't locate qdhr.exe, not launching the GUI." << std::endl;
      return;
    }

    wchar_t *lastSlash = wcsrchr(exepath.data(), '\\');

    if(lastSlash == NULL)
    {
      std::cerr << "  Couldn't locate qdhr.exe, not launching the GUI." << std::endl;
      return;
    }

    *lastSlash = 0;

    std::wstring qdhrexe = exepath.data();
    qdhrexe += L"/qdhr.exe";

    wchar_t params[512] = {0};

    _snwprintf_s(params, _countof(params), _TRUNCATE, L"\"%s\" --targetcontrol localhost:%u",
                 qdhrexe.c_str(), ident);

    STARTUPINFOW si;
    PROCESS_INFORMATION pi;
    ZeroMemory(&si, sizeof(si));
    ZeroMemory(&pi, sizeof(pi));
    si.cb = sizeof(si);

    if(!CreateProcessW(NULL, params, NULL, NULL, FALSE, 0, NULL, NULL, &si, &pi))
    {
      std::cerr << "  Failed to launch the GUI." << std::endl;
      return;
    }

    CloseHandle(pi.hThread);
    CloseHandle(pi.hProcess);

    std::cout << "  Launched the GUI connected to the target." << std::endl;
  }
};

// ignore the argc/argv we get here, convert from wide to be sure we're unicode safe.
int main(int, char *)
{
  LPWSTR *wargv;
  int argc;

  wargv = CommandLineToArgvW(GetCommandLine(), &argc);

  std::vector<std::string> argv;

  argv.resize(argc);
  for(size_t i = 0; i < argv.size(); i++)
    argv[i] = conv(std::wstring(wargv[i]));

  if(argv.empty())
    argv.push_back("dhrcmd");

  LocalFree(wargv);

  hInstance = GetModuleHandleA(NULL);

  WNDCLASSEX wc;
  wc.cbSize = sizeof(WNDCLASSEX);
  wc.style = 0;
  wc.lpfnWndProc = WndProc;
  wc.cbClsExtra = 0;
  wc.cbWndExtra = 0;
  wc.hInstance = hInstance;
  wc.hIcon = LoadIcon(NULL, MAKEINTRESOURCE(IDI_ICON));
  wc.hCursor = LoadCursor(NULL, IDC_ARROW);
  wc.hbrBackground = (HBRUSH)(COLOR_WINDOW + 1);
  wc.lpszMenuName = NULL;
  wc.lpszClassName = L"dhrcmd";
  wc.hIconSm = LoadIcon(NULL, MAKEINTRESOURCE(IDI_ICON));

  if(!RegisterClassEx(&wc))
  {
    return 1;
  }

  GlobalEnvironment env;

  // perform an upgrade of the UI
  add_command("upgrade", new UpgradeCommand());

#if CRASH_HANDLER
  // special WIN32 option for launching the crash handler
  add_command("crashhandle", new CrashHandlerCommand());
#endif

  // this installs a global windows hook pointing at dhrshim*.dll that filters all running
  // processes and loads dhr.dll in the target one. In any other process it unloads as soon as
  // possible
  add_command("globalhook", new GlobalHookCommand());

  // watches a running process and injects DHR into any child processes it spawns, without needing
  // DHR to be loaded into the watched process itself
  add_command("watch", new WatchCommand());

  return dhrcmd(env, argv);
}
