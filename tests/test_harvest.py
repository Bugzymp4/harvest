import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import unittest
import tempfile
import io
import subprocess
import harvest

class TestFindTag(unittest.TestCase):
    def test_finds_todo(self):
        self.assertEqual(harvest.find_tag("TODO: fix this"), "TODO")

    def test_finds_fixme(self):
        self.assertEqual(harvest.find_tag("FIXME: broken"), "FIXME")

    def test_finds_hack(self):
        self.assertEqual(harvest.find_tag("HACK around stdlib"), "HACK")

    def test_finds_xxx(self):
        self.assertEqual(harvest.find_tag("XXX remove me"), "XXX")

    def test_finds_note(self):
        self.assertEqual(harvest.find_tag("NOTE: see issue 42"), "NOTE")

    def test_case_insensitive(self):
        self.assertEqual(harvest.find_tag("todo: lower case"), "TODO")

    def test_no_match_returns_none(self):
        self.assertIsNone(harvest.find_tag("just a comment"))


class TestScanFileSingleLine(unittest.TestCase):
    def _write_temp(self, ext, content):
        f = tempfile.NamedTemporaryFile(
            mode="w", suffix=ext, delete=False, encoding="utf-8"
        )
        f.write(content)
        f.close()
        return f.name

    def test_python_hash_todo(self):
        path = self._write_temp(".py", "x = 1\n# TODO: fix this\ny = 2\n")
        lang = harvest.LANG_CONFIG[".py"]
        matches = harvest.scan_file(path, lang)
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0].tag, "TODO")
        self.assertEqual(matches[0].line_no, 2)
        self.assertIn("TODO", matches[0].content)
        os.unlink(path)

    def test_c_slash_fixme(self):
        path = self._write_temp(".c", "int x;\n// FIXME: bad alloc\nreturn 0;\n")
        lang = harvest.LANG_CONFIG[".c"]
        matches = harvest.scan_file(path, lang)
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0].tag, "FIXME")
        self.assertEqual(matches[0].line_no, 2)
        os.unlink(path)

    def test_plain_line_no_match(self):
        path = self._write_temp(".py", "x = 1\ny = 2\n")
        lang = harvest.LANG_CONFIG[".py"]
        matches = harvest.scan_file(path, lang)
        self.assertEqual(matches, [])
        os.unlink(path)

    def test_keyword_in_code_not_comment_ignored(self):
        # "TODO" inside a string, not a comment — should NOT match
        path = self._write_temp(".py", 'msg = "TODO: not a real comment"\n')
        lang = harvest.LANG_CONFIG[".py"]
        matches = harvest.scan_file(path, lang)
        self.assertEqual(matches, [])
        os.unlink(path)

    def test_lua_double_dash(self):
        path = self._write_temp(".lua", "-- NOTE: setup phase\nlocal x = 1\n")
        lang = harvest.LANG_CONFIG[".lua"]
        matches = harvest.scan_file(path, lang)
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0].tag, "NOTE")
        os.unlink(path)

    def test_inline_comment_after_code(self):
        path = self._write_temp(".py", 'x = get_value()  # TODO: validate\n')
        lang = harvest.LANG_CONFIG[".py"]
        matches = harvest.scan_file(path, lang)
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0].tag, "TODO")
        os.unlink(path)

    def test_c_inline_comment_after_code(self):
        path = self._write_temp(".c", 'int x = 1; // TODO: check bounds\n')
        lang = harvest.LANG_CONFIG[".c"]
        matches = harvest.scan_file(path, lang)
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0].tag, "TODO")
        os.unlink(path)


class TestScanFileBlock(unittest.TestCase):
    def _write_temp(self, ext, content):
        f = tempfile.NamedTemporaryFile(
            mode="w", suffix=ext, delete=False, encoding="utf-8"
        )
        f.write(content)
        f.close()
        return f.name

    def test_c_block_single_line(self):
        path = self._write_temp(".c", "/* TODO: fix alloc */\nint x;\n")
        lang = harvest.LANG_CONFIG[".c"]
        matches = harvest.scan_file(path, lang)
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0].tag, "TODO")
        self.assertEqual(matches[0].line_no, 1)
        os.unlink(path)

    def test_c_block_multiline(self):
        src = "/*\n * FIXME: this is broken\n * see issue 99\n */\nint x;\n"
        path = self._write_temp(".c", src)
        lang = harvest.LANG_CONFIG[".c"]
        matches = harvest.scan_file(path, lang)
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0].tag, "FIXME")
        self.assertEqual(matches[0].line_no, 2)
        os.unlink(path)

    def test_python_triple_double_quote_block(self):
        src = '"""\nNOTE: module initialises lazy\n"""\nx = 1\n'
        path = self._write_temp(".py", src)
        lang = harvest.LANG_CONFIG[".py"]
        matches = harvest.scan_file(path, lang)
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0].tag, "NOTE")
        self.assertEqual(matches[0].line_no, 2)
        os.unlink(path)

    def test_python_triple_single_quote_block(self):
        src = "'''\nHACK: workaround for bug\n'''\nx = 1\n"
        path = self._write_temp(".py", src)
        lang = harvest.LANG_CONFIG[".py"]
        matches = harvest.scan_file(path, lang)
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0].tag, "HACK")
        os.unlink(path)

    def test_lua_block(self):
        src = "--[[\nXXX: remove before release\n]]\nlocal x = 1\n"
        path = self._write_temp(".lua", src)
        lang = harvest.LANG_CONFIG[".lua"]
        matches = harvest.scan_file(path, lang)
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0].tag, "XXX")
        os.unlink(path)

    def test_no_match_in_normal_code(self):
        path = self._write_temp(".c", "int x = 0;\nreturn x;\n")
        lang = harvest.LANG_CONFIG[".c"]
        matches = harvest.scan_file(path, lang)
        self.assertEqual(matches, [])
        os.unlink(path)


class TestScanDir(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir)

    def _write(self, rel_path, content):
        full = os.path.join(self.tmpdir, rel_path)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, "w") as f:
            f.write(content)

    def test_finds_matches_recursively(self):
        self._write("src/main.py", "# TODO: write main\nx = 1\n")
        self._write("src/lib.py", "# FIXME: broken\ny = 2\n")
        matches = harvest.scan_dir(self.tmpdir)
        tags = {m.tag for m in matches}
        self.assertIn("TODO", tags)
        self.assertIn("FIXME", tags)

    def test_skips_node_modules(self):
        self._write("node_modules/lib.js", "// TODO: upstream bug\n")
        self._write("src/app.js", "// NOTE: entry point\n")
        matches = harvest.scan_dir(self.tmpdir)
        files = {m.file for m in matches}
        self.assertFalse(any("node_modules" in f for f in files))

    def test_skips_git_dir(self):
        self._write(".git/COMMIT_EDITMSG", "# TODO: ignored\n")
        self._write("main.py", "# NOTE: real\n")
        matches = harvest.scan_dir(self.tmpdir)
        files = {m.file for m in matches}
        self.assertFalse(any(".git" in f for f in files))

    def test_ignores_unknown_extension(self):
        self._write("README.md", "TODO: update docs\n")
        matches = harvest.scan_dir(self.tmpdir)
        self.assertEqual(matches, [])

    def test_tag_filter(self):
        self._write("a.py", "# TODO: one\n# FIXME: two\n")
        matches = harvest.scan_dir(self.tmpdir, tag_filter="TODO")
        self.assertTrue(all(m.tag == "TODO" for m in matches))
        self.assertEqual(len(matches), 1)


class TestRender(unittest.TestCase):
    def _matches(self):
        return [
            harvest.Match("/proj/src/main.py", 10, "TODO",  "# TODO: fix edge case"),
            harvest.Match("/proj/src/auth.py",  5,  "FIXME", "# FIXME: leaks memory"),
            harvest.Match("/proj/src/main.py", 42, "NOTE",  "# NOTE: see RFC 1234"),
        ]

    def test_render_terminal_groups_by_tag(self):
        matches = self._matches()
        buf = io.StringIO()
        old_stdout = sys.stdout
        sys.stdout = buf
        try:
            harvest.render_terminal(matches, "/proj")
        finally:
            sys.stdout = old_stdout
        out = buf.getvalue()
        self.assertIn("TODO", out)
        self.assertIn("FIXME", out)
        self.assertIn("NOTE", out)
        # TODO appears before FIXME in TAGS order
        self.assertLess(out.index("TODO"), out.index("FIXME"))

    def test_render_terminal_empty(self):
        buf = io.StringIO()
        old_stdout = sys.stdout
        sys.stdout = buf
        try:
            harvest.render_terminal([], "/proj")
        finally:
            sys.stdout = old_stdout
        self.assertIn("No annotations found", buf.getvalue())

    def test_render_file_plain_text(self):
        matches = self._matches()
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            out_path = f.name
        harvest.render_file(matches, "/proj", out_path)
        with open(out_path) as f:
            content = f.read()
        os.unlink(out_path)
        self.assertIn("TODO", content)
        self.assertIn("FIXME", content)
        self.assertNotIn("\033[", content)  # no ANSI escape codes

    def test_render_file_empty(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            out_path = f.name
        harvest.render_file([], "/proj", out_path)
        with open(out_path) as f:
            content = f.read()
        os.unlink(out_path)
        self.assertIn("No annotations found", content)

HARVEST = os.path.join(os.path.dirname(__file__), "..", "harvest.py")


class TestCLI(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir)

    def _write(self, rel_path, content):
        full = os.path.join(self.tmpdir, rel_path)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, "w") as f:
            f.write(content)
        return full

    def _run(self, *args):
        return subprocess.run(
            [sys.executable, HARVEST] + list(args),
            capture_output=True, text=True
        )

    def test_default_path_is_cwd(self):
        self._write("main.py", "# TODO: test default path\n")
        result = self._run("--path", self.tmpdir)
        self.assertEqual(result.returncode, 0)
        self.assertIn("TODO", result.stdout)

    def test_type_filter(self):
        self._write("a.py", "# TODO: one\n# FIXME: two\n")
        result = self._run("--path", self.tmpdir, "--type", "todo")
        self.assertIn("TODO", result.stdout)
        self.assertNotIn("FIXME", result.stdout)

    def test_output_flag_writes_file(self):
        self._write("a.py", "# NOTE: hello\n")
        out_file = os.path.join(self.tmpdir, "report.txt")
        result = self._run("--path", self.tmpdir, "--output", out_file)
        self.assertEqual(result.returncode, 0)
        self.assertTrue(os.path.exists(out_file))
        with open(out_file) as f:
            content = f.read()
        self.assertIn("NOTE", content)
        self.assertNotIn("\033[", content)

    def test_invalid_path_exits_nonzero(self):
        result = self._run("--path", "/nonexistent/path/xyz")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("error", result.stderr.lower())

    def test_invalid_type_exits_nonzero(self):
        result = self._run("--path", self.tmpdir, "--type", "BADTAG")
        self.assertNotEqual(result.returncode, 0)

    def test_no_matches_prints_message(self):
        self._write("a.py", "x = 1\n")
        result = self._run("--path", self.tmpdir)
        self.assertEqual(result.returncode, 0)
        self.assertIn("No annotations found", result.stdout)


if __name__ == "__main__":
    unittest.main()
