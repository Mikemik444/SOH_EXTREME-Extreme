// SOH_EXTREME_SEGMENT_GUARD: a tagged address must identify one of the 16
// segment slots before indexing. Do not truncate a corrupt 64-bit address.
void* Interpreter::SegAddr(uintptr_t w1) {
    if (w1 & 1) {
        const uintptr_t segNum = w1 >> 24;
        const uintptr_t offset = w1 & 0x00FFFFFE;
        if (segNum >= MAX_SEGMENT_POINTERS) {
            throw SohExtremeInvalidGfx{ "segment index", segNum, w1 };
        }
        const uintptr_t base = mSegmentPointers[segNum];
        if (base == 0) {
            throw SohExtremeInvalidGfx{ "unbound segment", segNum, w1 };
        }
        if (base > UINTPTR_MAX - offset) {
            throw SohExtremeInvalidGfx{ "segment address overflow", base, offset };
        }
        return reinterpret_cast<void*>(base + offset);
    }
    // Native aligned addresses are already resolved; preserve that convention.
    return reinterpret_cast<void*>(w1);
}
