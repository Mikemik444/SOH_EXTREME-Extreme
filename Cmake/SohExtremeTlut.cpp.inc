// SOH_EXTREME_TLUT_COMPLETE_GUARD: validate/copy the whole transfer before
// publishing either palette half. ReadProcessMemory safely fails if a source
// page becomes inaccessible; a VirtualQuery followed by memcpy can race.
static bool SohExtremeCopyTlut(uint8_t* dst, const uint8_t* src, size_t bytes) {
    if (src == nullptr || bytes == 0 || bytes > 512 ||
        reinterpret_cast<uintptr_t>(src) > UINTPTR_MAX - bytes) return false;
#ifdef _WIN32
    SIZE_T copied = 0;
    return ReadProcessMemory(GetCurrentProcess(), src, dst, bytes, &copied) != 0 && copied == bytes;
#else
    memcpy(dst, src, bytes);
    return true;
#endif
}

void Interpreter::GfxDpLoadTlut(uint8_t tile, uint32_t high_index) {
    if (tile >= 8 || high_index >= 256 || mRdp->texture_to_load.siz != G_IM_SIZ_16b) return;
    const uint16_t tmem = mRdp->texture_tile[tile].tmem;
    if (tmem >= 512) return;
    const uint8_t* src = mRdp->texture_to_load.addr;
    const uint32_t byteCount = (high_index + 1) * 2;
    // Keep the legacy nonstandard lower-TMEM fallback in the second palette
    // half, but stage it too instead of retaining an unchecked source pointer.
    const uint32_t paletteOffset = tmem >= 256 ? (tmem - 256) * 2 : 256;
    const uint32_t copyLen = std::min(byteCount, 512u - paletteOffset);
    uint8_t transfer[512];
    if (!SohExtremeCopyTlut(transfer, src, copyLen)) {
        // Rate-limit malformed display lists without hiding the first report.
        static unsigned reports = 0;
        if (reports++ < 8) SPDLOG_ERROR("SOH-EXTREME: rejected unreadable TLUT source {:p}, {} bytes, tile {}, tmem {}",
            static_cast<const void*>(src), copyLen, tile, tmem);
        return;
    }
    uint32_t copied = 0;
    while (copied < copyLen) {
        const uint32_t destination = paletteOffset + copied;
        const uint32_t half = destination / 256;
        const uint32_t offset = destination % 256;
        const uint32_t size = std::min(copyLen - copied, 256u - offset);
        memcpy(mRdp->palette_staging[half] + offset, transfer + copied, size);
        mRdp->palettes[half] = mRdp->palette_staging[half];
        mRdp->palette_dram_addr[half] = src + copied;
        copied += size;
    }
}

