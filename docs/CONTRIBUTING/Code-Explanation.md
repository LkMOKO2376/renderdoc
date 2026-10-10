# Code Explanation

This is a rough 'table of contents' overview of how the main code components are organised:

    dhr/ 
        CMakeLists.txt           ; The cmake file, will recurse into subdirectories to build them
        dhr.sln            ; VS2015 solution for windows building
        dhr/
            3rdparty/            ; third party utilities & libraries included
            drivers/             ; API-specific back-ends, can be individually skipped/removed
            ...                  ; everything else in here consists of the core dhr runtime
        dhrcmd/            ; A small C++ utility program that runs to do various little tasks
        dhrshim/           ; A tiny C DLL using only kernel32.dll that is used for global hooking
        qdhr/              ; The Qt UI layer built on top of dhr/
        docs/                    ; source documentation for the .chm file or http://docs.renderdoc.org/
        util/                    ; folder for utility/support files - e.g. build scripts, installers, CI config
