from gitrelay.io import readlines_backwards


def test_readlines_backwards_empty_file(tmp_path):
    """Verifies reading from an empty file returns nothing."""
    p = tmp_path / "empty.txt"
    p.touch()
    assert list(readlines_backwards(p)) == []


def test_readlines_backwards_single_line(tmp_path):
    """Verifies reading from a single line file."""
    p = tmp_path / "single.txt"
    p.write_text("hello")
    assert list(readlines_backwards(p)) == ["hello"]


def test_readlines_backwards_single_line_with_newline(tmp_path):
    """Verifies reading from a single line file with trailing newline."""
    p = tmp_path / "single_nl.txt"
    p.write_text("hello\n")
    assert list(readlines_backwards(p)) == ["hello"]


def test_readlines_backwards_multiple_lines(tmp_path):
    """Verifies reading multiple lines in reverse order."""
    p = tmp_path / "multi.txt"
    p.write_text("line1\nline2\nline3")
    assert list(readlines_backwards(p)) == ["line3", "line2", "line1"]


def test_readlines_backwards_multiple_lines_with_trailing_newline(tmp_path):
    """Verifies reading multiple lines with trailing newline in reverse order."""
    p = tmp_path / "multi_nl.txt"
    p.write_text("line1\nline2\nline3\n")
    assert list(readlines_backwards(p)) == ["line3", "line2", "line1"]


def test_readlines_backwards_with_empty_lines(tmp_path):
    """Verifies reading with intermediate empty lines."""
    p = tmp_path / "empty_lines.txt"
    p.write_text("line1\n\nline3\n")
    assert list(readlines_backwards(p)) == ["line3", "", "line1"]


def test_readlines_backwards_no_strip(tmp_path):
    """Verifies reading without stripping line endings."""
    p = tmp_path / "no_strip.txt"
    p.write_text("line1\nline2\n")
    # Note: our current implementation always adds \n if strip_line_endings is False
    # and the logic might yield it slightly differently than original file
    assert list(readlines_backwards(p, strip_line_endings=False)) == [
        "line2\n",
        "line1\n",
    ]
