from pathlib import Path
import os, tempfile, zipfile
_temporary = None

def ap_source(root: Path) -> Path:
    global _temporary
    override = os.environ.get('SOH_TEST_AP_SOURCE')
    if override:
        path=Path(override)
        return path/'soh_extreme' if (path/'soh_extreme').is_dir() else path
    if (root/'ap/soh_extreme').is_dir(): return root/'ap/soh_extreme'
    _temporary=tempfile.TemporaryDirectory(prefix='soh-tracker-tests-')
    dest=Path(_temporary.name)
    with zipfile.ZipFile(root/'source/soh_extreme-source.zip') as archive:
        for entry in archive.infolist():
            target=(dest/entry.filename).resolve()
            if not target.is_relative_to(dest.resolve()):raise ValueError('Unsafe source archive path')
        archive.extractall(dest)
    return dest/'soh_extreme'
