// SOH_EXTREME_RAW_CRASH_STACK: retain real addresses even without shipped PDBs.
void CrashHandler::PrintStack(CONTEXT* ctx) {
#ifndef _M_ARM64
    CONTEXT copy = *ctx;
    PrintRegisters(&copy);
    HANDLE process = GetCurrentProcess();
    HANDLE thread = GetCurrentThread();
    SymSetOptions(SYMOPT_NO_IMAGE_SEARCH | SYMOPT_IGNORE_IMAGEDIR);
    const bool symbolsReady = SymInitialize(process, "debug", TRUE) != FALSE;
    STACKFRAME64 stack{};
#if defined(_M_AMD64)
    constexpr DWORD machine = IMAGE_FILE_MACHINE_AMD64;
    stack.AddrPC.Offset = copy.Rip;
    stack.AddrStack.Offset = copy.Rsp;
    stack.AddrFrame.Offset = copy.Rbp;
#else
    constexpr DWORD machine = IMAGE_FILE_MACHINE_I386;
    stack.AddrPC.Offset = copy.Eip;
    stack.AddrStack.Offset = copy.Esp;
    stack.AddrFrame.Offset = copy.Ebp;
#endif
    stack.AddrPC.Mode = stack.AddrStack.Mode = stack.AddrFrame.Mode = AddrModeFlat;
    AppendLine("Traceback (actual PC, module base and RVA):");
    for (unsigned frame = 0; frame < 64 && stack.AddrPC.Offset != 0; ++frame) {
        alignas(SYMBOL_INFO) char storage[sizeof(SYMBOL_INFO) + MAX_SYM_NAME]{};
        auto* symbol = reinterpret_cast<SYMBOL_INFO*>(storage);
        symbol->SizeOfStruct = sizeof(SYMBOL_INFO);
        symbol->MaxNameLen = MAX_SYM_NAME;
        DWORD64 displacement = 0;
        const bool named = symbolsReady && SymFromAddr(process, stack.AddrPC.Offset, &displacement, symbol);
        HMODULE module = nullptr;
        char modulePath[MAX_PATH]{};
        GetModuleHandleExA(GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS | GET_MODULE_HANDLE_EX_FLAG_UNCHANGED_REFCOUNT,
                          reinterpret_cast<LPCSTR>(stack.AddrPC.Offset), &module);
        if (module) GetModuleFileNameA(module, modulePath, MAX_PATH);
        const DWORD64 base = reinterpret_cast<DWORD64>(module);
        char row[160];
        snprintf(row, sizeof(row), "    #%u PC=0x%016llX base=0x%016llX RVA=0x%llX ",
                 frame, stack.AddrPC.Offset, base, base ? stack.AddrPC.Offset - base : 0);
        AppendStr(row);
        AppendStr(named ? symbol->Name : "<unresolved>");
        AppendStr(" in ");
        AppendLine(module ? modulePath : "<unknown module>");
        const DWORD64 pc = stack.AddrPC.Offset, sp = stack.AddrStack.Offset;
        if (!StackWalk64(machine, process, thread, &stack, &copy, nullptr,
                         SymFunctionTableAccess64, SymGetModuleBase64, nullptr)) break;
        // DbgHelp's first step can describe the current frame again. Advance
        // once more before treating an unchanged frame as a broken unwind.
        if (pc == stack.AddrPC.Offset && sp == stack.AddrStack.Offset) {
            if (frame != 0 || !StackWalk64(machine, process, thread, &stack, &copy, nullptr,
                              SymFunctionTableAccess64, SymGetModuleBase64, nullptr) ||
                (pc == stack.AddrPC.Offset && sp == stack.AddrStack.Offset)) break;
        }
    }
    if (symbolsReady) SymCleanup(process);
    PrintCommon();
    Context::GetRawInstance()->GetLogger()->flush();
    spdlog::shutdown();
#endif
}
