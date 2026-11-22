"""Write the generated log fixture to a file (reference for fixtures.js).

    python -m tests.browser.make_fixture --lines 1000000 --eol lf --out fx.log

Line ``i`` (1-based) is ``line_editor.sample.sample_line(i)`` followed by a line
break. ``--eol mixed`` ends line ``i`` with CRLF when the i-th output of
``mulberry32(seed)`` is odd and with LF otherwise. The same bytes come out of
``fixtureChunks`` in ``fixtures.js``.
"""

import argparse
import hashlib
import sys

from line_editor.sample import sample_line

MASK = 0xFFFFFFFF
CHUNK_LINES = 8192
BOM = b"\xef\xbb\xbf"


def mulberry32(seed):
    """Yield the 32-bit outputs of mulberry32(seed), as prng.js does."""
    a = seed & MASK
    while True:
        a = (a + 0x6D2B79F5) & MASK
        t = ((a ^ (a >> 15)) * (1 | a)) & MASK
        t = (((t + (((t ^ (t >> 7)) * (61 | t)) & MASK)) & MASK) ^ t) & MASK
        yield (t ^ (t >> 14)) & MASK


def fixture_blocks(lines, eol="lf", bom=False, seed=7):
    """Yield the fixture as byte blocks of bounded size."""
    if eol not in ("lf", "crlf", "mixed"):
        raise ValueError("eol must be lf, crlf or mixed")
    if bom:
        yield BOM
    rng = mulberry32(seed) if eol == "mixed" else None
    parts = []
    for i in range(1, lines + 1):
        if eol == "lf":
            end = "\n"
        elif eol == "crlf":
            end = "\r\n"
        else:
            end = "\r\n" if next(rng) & 1 else "\n"
        parts.append(sample_line(i) + end)
        if len(parts) >= CHUNK_LINES:
            yield "".join(parts).encode("utf-8")
            parts = []
    if parts:
        yield "".join(parts).encode("utf-8")


def main(argv=None):
    parser = argparse.ArgumentParser(prog="python -m tests.browser.make_fixture")
    parser.add_argument("--lines", type=int, required=True)
    parser.add_argument("--eol", choices=("lf", "crlf", "mixed"), required=True)
    parser.add_argument("--bom", action="store_true")
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--out", required=True)
    args = parser.parse_args(argv)
    if args.lines < 0:
        parser.error("--lines must not be negative")
    digest = hashlib.sha256()
    total = 0
    with open(args.out, "wb") as handle:
        for block in fixture_blocks(args.lines, args.eol, args.bom, args.seed):
            handle.write(block)
            digest.update(block)
            total += len(block)
    print(total)
    print(digest.hexdigest())
    return 0


if __name__ == "__main__":
    sys.exit(main())
