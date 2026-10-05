// SOH_EXTREME_VERTEX_GUARD: unwind only a rejected graphics command, never an
// arbitrary engine exception. Keep these checks active in Release builds.
struct SohExtremeInvalidGfx {
    const char* reason;
    size_t first;
    size_t second;
};

static void SohExtremeCheckVertexRange(size_t start, size_t count, size_t capacity) {
    // Subtract after checking start: malformed F3DEX2 commands can underflow
    // their destination index, and filepath commands carry full-width counts.
    if (start > capacity || count > capacity - start) {
        throw SohExtremeInvalidGfx{ "vertex range", start, count };
    }
}

static void SohExtremeCheckVertexLoad(size_t start, size_t count, const F3DVtx* vertices) {
    SohExtremeCheckVertexRange(start, count, MAX_VERTICES);
    if (count != 0 && vertices == nullptr) {
        throw SohExtremeInvalidGfx{ "null vertex source", start, count };
    }
}

