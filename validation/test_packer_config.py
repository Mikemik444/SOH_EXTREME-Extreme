"""Isolated CMake tests with a MOCK packer; not a game/codec/MSVC test.

The PowerShell edit plan is tested using its actual regex strings in Python.
The generated CMake modules are then executed by CMake on this platform.
The PowerShell process itself still needs Windows validation.
"""
from pathlib import Path
import json
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = (ROOT / 'Fix-PackerPath.ps1').read_text()
OLD_BLOCK = (ROOT / 'validation/fixtures/OriginalAssetTargets.cmake.txt').read_text()
INCLUDE = re.search(r"\$Include = '([^']+)'", SCRIPT)[1]
FILTER = re.search(r"\$Filter = '([^']+)'", SCRIPT)[1]
PATTERN = re.search(r"\$Pattern = '([^']+)'", SCRIPT)[1]
GLOB_PATTERN = re.search(r"\[regex\]::Matches\(\$Text, '([^']+)'\)", SCRIPT)[1]

HEAD = '''cmake_minimum_required(VERSION 3.26)
project(soh VERSION 9.2.3 LANGUAGES CXX)
add_library(torch INTERFACE)
add_library(libultraship INTERFACE)
file(GLOB_RECURSE soh__ CONFIGURE_DEPENDS RELATIVE ${CMAKE_CURRENT_SOURCE_DIR} "soh/*.cpp")
add_executable(soh ${soh__})
set_target_properties(soh PROPERTIES RUNTIME_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}/bin")
# unrelated settings sentinel -- must stay unchanged
'''
MOCK_PACKER = r'''
#include <filesystem>
#include <fstream>
#include <string>
int main(int argc, char** argv) {
    if (argc != 4) return 11;
    const std::filesystem::path source(argv[1]);
    if (!std::filesystem::exists(source / "objects/base.txt") ||
        !std::filesystem::exists(source / "textures/portrait.txt") ||
        !std::filesystem::exists(source / "shaders/test.glsl")) return 12;
    std::string texture;
    std::ifstream(source / "textures/portrait.txt") >> texture;
    if (texture != "patched-portrait") return 13;
    std::ofstream out(argv[2]);
    out << "MOCK archive contains full base, patched portrait, shader; " << argv[3];
    return out ? 0 : 14;
}
'''

def patch_plan(text):
    original = text
    text = text.replace('\r\n', '\n')
    if INCLUDE not in text:
        matches = list(re.finditer(PATTERN, text))
        if len(matches) != 1: raise ValueError('unexpected asset block')
        match = matches[0]
        text = text[:match.start()] + INCLUDE + text[match.end():]
    if FILTER not in text:
        matches = list(re.finditer(GLOB_PATTERN, text))
        if len(matches) != 1: raise ValueError('unexpected glob')
        position = matches[0].end()
        text = text[:position] + '\n# Build tools belong to their own executables.\n' + FILTER + text[position:]
    return text.replace('\n', '\r\n') if '\r\n' in original else text

def run(*args):
    return subprocess.run([str(a) for a in args], text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=40)

class PackerTests(unittest.TestCase):
    def make_project(self, root, layout):
        root.mkdir(parents=True)
        for path, data in {
            'soh/game.cpp': 'int main() { return 0; }\n',
            'soh/assets/tools/torch-cli/main.cpp': '#error Must not be compiled into soh\n',
            'src/fast/shaders/test.glsl': 'mock shader',
            'soh/assets/custom/objects/base.txt': 'base object',
            'soh/assets/custom/textures/portrait.txt': 'old-portrait',
            'assets/custom/textures/portrait.txt': 'patched-portrait',
            f'{layout}/main.cpp': MOCK_PACKER,
            f'{layout}/PngTexture.cpp': '// mock texture conversion translation unit\n',
            f'{layout}/PngTexture.h': '// mock header\n',
        }.items():
            path = root / path
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(data)
        shutil.copytree(ROOT / 'tools', root / 'tools')
        (root / 'CMakeLists.txt').write_text(HEAD + OLD_BLOCK)

    def test_patch_plan_is_idempotent_for_lf_and_crlf(self):
        for newline in ('\n', '\r\n'):
            original = (HEAD + OLD_BLOCK).replace('\n', newline)
            patched = patch_plan(original)
            self.assertEqual(patch_plan(patched), patched)
            self.assertEqual(patched.count(INCLUDE), 1)
            self.assertEqual(patched.count(FILTER), 1)
            self.assertIn('# unrelated settings sentinel -- must stay unchanged', patched)
            self.assertNotIn('add_executable(soh-o2r-packer', patched)

    def test_unknown_or_duplicate_blocks_are_rejected(self):
        for contents in ('not CMake', HEAD + OLD_BLOCK + OLD_BLOCK, OLD_BLOCK):
            with self.assertRaises(ValueError): patch_plan(contents)

    def test_original_error_and_fixed_nested_layout_build(self):
        with tempfile.TemporaryDirectory(prefix='soh source test ') as temp:
            source = Path(temp) / 'source'
            self.make_project(source, 'soh/assets/tools/soh-o2r-packer')
            bad = run('cmake', '-S', source, '-B', Path(temp) / 'old-build')
            self.assertNotEqual(bad.returncode, 0)
            self.assertIn('assets/tools/soh-o2r-packer/main.cpp', bad.stdout)
            self.assertIn('Cannot find source file', bad.stdout)
            self.verify_fixed_build(source, Path(temp) / 'new-build')

    def test_fixed_legacy_root_layout_build(self):
        with tempfile.TemporaryDirectory(prefix='soh root test ') as temp:
            source = Path(temp) / 'source'
            self.make_project(source, 'assets/tools/soh-o2r-packer')
            self.verify_fixed_build(source, Path(temp) / 'build')

    def verify_fixed_build(self, source, build):
        path = source / 'CMakeLists.txt'
        path.write_text(patch_plan(path.read_text()))
        configured = run('cmake', '-S', source, '-B', build)
        self.assertEqual(configured.returncode, 0, configured.stdout)
        # Actually compile the mock packer/game and run GenerateSohOtr's CMake
        # staging commands. The torch-cli #error catches source-glob regression.
        built = run('cmake', '--build', build, '--target', 'soh', 'GenerateSohOtr', '--parallel', '1')
        self.assertEqual(built.returncode, 0, built.stdout)
        self.assertIn('MOCK archive', (build / 'soh/soh.o2r').read_text())
        self.assertEqual((source / 'soh/assets/custom/textures/portrait.txt').read_text(), 'old-portrait')
        self.assertEqual((source / 'assets/custom/textures/portrait.txt').read_text(), 'patched-portrait')

    @unittest.skipIf(sys.platform == 'win32', 'POSIX executable stub used for negative pack tests')
    def test_failed_or_empty_pack_preserves_existing_output(self):
        with tempfile.TemporaryDirectory(prefix='soh pack failures ') as temp:
            root = Path(temp)
            source = root / 'source'
            self.make_project(source, 'soh/assets/tools/soh-o2r-packer')
            output = root / 'build/soh/soh.o2r'
            output.parent.mkdir(parents=True)
            packer = root / 'mock-packer'
            for body in ('raise SystemExit(9)', 'open(sys.argv[2], "w").close()'):
                with self.subTest(body=body):
                    output.write_text('previous-good-archive')
                    packer.write_text('#!' + sys.executable + '\nimport sys\n' + body + '\n')
                    packer.chmod(0o755)
                    result = run('cmake', f'-DSOH_SOURCE_ROOT={source}', f'-DSOH_BUILD_ROOT={root / "build"}',
                        f'-DSOH_SHADER_DIR={source / "src/fast/shaders"}', f'-DSOH_PACKER={packer}',
                        '-DSOH_PORT_VERSION=9.2.3', '-P', ROOT / 'tools/cmake/PackSohExtremeAssets.cmake')
                    self.assertNotEqual(result.returncode, 0, result.stdout)
                    self.assertEqual(output.read_text(), 'previous-good-archive')

if __name__ == '__main__':
    unittest.main(verbosity=2)
