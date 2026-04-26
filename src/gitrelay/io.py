# Copyright (c) 2026 Luís Gomes <https://luismsgomes.github.io/>

import os
from pathlib import Path
from typing import Generator


def readlines_backwards(
    path: Path, strip_line_endings: bool = True
) -> Generator[str, None, None]:
    """
    Yields lines from a file in reverse order (from end to start).

    Uses binary seeking for efficiency on large files.
    """
    if not path.exists():
        return

    with open(path, "rb") as f:
        f.seek(0, os.SEEK_END)
        pointer = f.tell()
        if pointer == 0:
            return

        buffer = bytearray()
        # If the file ends with a newline, we want to skip that first empty split result
        trailing_newline_handled = False

        while pointer > 0:
            step = min(pointer, 4096)
            pointer -= step
            f.seek(pointer)
            chunk = f.read(step)
            
            buffer = chunk + buffer
            lines = buffer.split(b"\n")
            
            # The first element might be incomplete, keep it for next iteration
            if pointer > 0:
                buffer = lines[0]
                to_yield = lines[1:]
            else:
                buffer = bytearray()
                to_yield = lines

            for line in reversed(to_yield):
                if not trailing_newline_handled:
                    trailing_newline_handled = True
                    if not line:
                        continue
                
                line_str = line.decode("utf-8")
                if strip_line_endings:
                    yield line_str.rstrip("\r\n")
                else:
                    yield line_str + "\n"

        if buffer:
            line_str = buffer.decode("utf-8")
            if strip_line_endings:
                yield line_str.rstrip("\r\n")
            else:
                yield line_str
