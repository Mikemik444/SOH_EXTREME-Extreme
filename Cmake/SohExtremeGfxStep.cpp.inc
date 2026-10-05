// SOH_EXTREME_GFX_STEP: a bad command invalidates the remainder of this frame.
// Capture raw words before a handler can advance a multiword command. Do not
// dereference a corrupt resource pointer while writing the diagnostic.
static bool SohExtremeGfxStep() {
    const auto* cmd = g_exec_stack.currCmd();
    const auto w0 = cmd->words.w0;
    const auto w1 = cmd->words.w1;
    try {
        gfx_step();
        return true;
    } catch (const SohExtremeInvalidGfx& fault) {
        static uint64_t rejectedFrames = 0;
        if (rejectedFrames != UINT64_MAX) {
            ++rejectedFrames;
        }
        // A persistent bad model must not fill the log every rendered frame.
        if (rejectedFrames <= 8 || (rejectedFrames & (rejectedFrames - 1)) == 0) {
            SPDLOG_ERROR("[SOH-EXTREME] Rejected graphics frame #{}: {} ({}, {}), "
                         "cmd=0x{:X} w0=0x{:X} w1=0x{:X} ucode={} depth={}",
                         rejectedFrames, fault.reason, fault.first, fault.second,
                         reinterpret_cast<uintptr_t>(cmd), w0, w1,
                         static_cast<uint32_t>(ucode_handler_index), g_exec_stack.cmd_stack.size());
            // Addresses identify the display-list callers without trusting
            // embedded filenames or reading the callers' command data.
            const auto& path = g_exec_stack.gfx_path;
            const size_t begin = path.size() > 8 ? path.size() - 8 : 0;
            for (size_t i = begin; i < path.size(); ++i) {
                SPDLOG_ERROR("[SOH-EXTREME] Graphics caller {}: 0x{:X}", i,
                             reinterpret_cast<uintptr_t>(path[i]));
            }
        }
        g_exec_stack.stop();
        g_exec_stack.disp_stack.clear();
        return false;
    }
}

