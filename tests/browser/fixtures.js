/* Seeded log fixture for the browser harness (test-only; never in STATIC_FILES).
 *
 * Classic script, no DOM access (a worker may importScripts() it after
 * prng.js). Reference: line_editor/sample.py:sample_line and
 * tests/browser/make_fixture.py, which writes the same bytes to a file.
 *
 *   fixtureLine(i)                  line i (1-based), no line break
 *   fixtureChunks(lines, opts)      Array of strings, each far below 1 MiB
 *       opts.eol   'lf' (default), 'crlf' or 'mixed'
 *       opts.bom   true puts U+FEFF first in the first chunk (EF BB BF)
 *       opts.seed  mixed only (default 7): line i ends with CRLF when the
 *                  i-th nextU32() of mulberry32(seed) is odd, else LF
 *   sha256OfChunks(chunks)          Promise<hex string>
 *   digestChunks(chunks)            Promise<{sha256, bytes}>
 *
 * Every line ends with a break, the last one too. Hours are not wrapped
 * (line 500000 starts 2026-01-01T138:...) and event=NNN is zero-padded to
 * three digits only, exactly as in the Python reference.
 */
(function (global) {
  'use strict';

  // 8192 lines are at most about 8192 * 63 = 516,000 UTF-16 units for the
  // 7-digit line numbers of the 5,000,000-line fixture: about half of 1 MiB.
  var CHUNK_LINES = 8192;
  var MAX_CHUNK_UNITS = 1048576;
  var BOM = '\uFEFF';

  function pad(n, width) {
    var s = String(n);
    while (s.length < width) s = '0' + s;
    return s;
  }

  function level(i) {
    if (i % 25 === 0) return 'ERROR';
    if (i % 10 === 0) return 'WARN';
    return 'INFO';
  }

  function fixtureLine(i) {
    if (!Number.isInteger(i) || i < 1) {
      throw new RangeError('fixtureLine(i) needs an integer i >= 1, got ' + i);
    }
    var s = i - 1;
    return '2026-01-01T' + pad(Math.floor(s / 3600), 2) + ':' +
      pad(Math.floor(s / 60) % 60, 2) + ':' + pad(s % 60, 2) + 'Z ' +
      'service-' + (i % 4) + ' ' + level(i) + ' event=' + pad(i, 3) +
      ' value=' + ((i * 37) % 101);
  }

  function fixtureChunks(lines, options) {
    var o = options || {};
    var eol = o.eol === undefined ? 'lf' : o.eol;
    var seed = o.seed === undefined ? 7 : o.seed;
    var bom = o.bom === true;
    if (!Number.isInteger(lines) || lines < 0) {
      throw new RangeError('fixtureChunks(lines) needs an integer >= 0, got ' + lines);
    }
    if (eol !== 'lf' && eol !== 'crlf' && eol !== 'mixed') {
      throw new RangeError("eol must be 'lf', 'crlf' or 'mixed', got " + eol);
    }
    var rng = eol === 'mixed' ? global.mulberry32(seed) : null;
    var chunks = [];
    var parts = [];

    function flush() {
      var text = parts.join('');
      if (bom && chunks.length === 0) text = BOM + text;
      chunks.push(text);
      parts = [];
    }

    for (var i = 1; i <= lines; i++) {
      var end;
      if (eol === 'lf') end = '\n';
      else if (eol === 'crlf') end = '\r\n';
      else end = (rng.nextU32() & 1) ? '\r\n' : '\n';
      parts.push(fixtureLine(i) + end);
      if (parts.length === CHUNK_LINES) flush();
    }
    if (parts.length > 0) flush();
    if (chunks.length === 0 && bom) chunks.push(BOM);
    return chunks;
  }

  function toHex(buffer) {
    return Array.from(new Uint8Array(buffer), function (b) {
      return b.toString(16).padStart(2, '0');
    }).join('');
  }

  // UTF-8 encodes chunk by chunk (no string longer than one chunk is ever
  // built), joins the bytes into one Uint8Array of the exact length and
  // hashes it.
  async function digestChunks(chunks) {
    var encoder = new TextEncoder();
    var encoded = new Array(chunks.length);
    var total = 0;
    for (var k = 0; k < chunks.length; k++) {
      if (chunks[k].length > MAX_CHUNK_UNITS) {
        throw new RangeError('chunk ' + k + ' is longer than 1 MiB');
      }
      encoded[k] = encoder.encode(chunks[k]);
      total += encoded[k].length;
    }
    var all = new Uint8Array(total);
    var offset = 0;
    for (var j = 0; j < encoded.length; j++) {
      all.set(encoded[j], offset);
      offset += encoded[j].length;
      encoded[j] = null;
    }
    var digest = await crypto.subtle.digest('SHA-256', all);
    return { sha256: toHex(digest), bytes: total };
  }

  async function sha256OfChunks(chunks) {
    return (await digestChunks(chunks)).sha256;
  }

  global.fixtureLine = fixtureLine;
  global.fixtureChunks = fixtureChunks;
  global.sha256OfChunks = sha256OfChunks;
  global.digestChunks = digestChunks;
})(globalThis);
