/* Seeded generator for the browser harness (test-only; never in STATIC_FILES).
 *
 * Classic script, no DOM access, so a worker may importScripts() it.
 *
 *   var rng = mulberry32(7);
 *   rng.nextU32();    // unsigned 32-bit integer in [0, 2^32)
 *   rng.nextFloat();  // nextU32() / 2^32, in [0, 1)
 *   rng.nextInt(n);   // integer in [0, n), for integer 1 <= n <= 2^32
 *
 * The Python reference is mulberry32() in tests/browser/make_fixture.py. The
 * first three outputs per seed are pinned by selftest.js and by the Python
 * tests (seed 7: 50271532, 266108690, 4195786334).
 *
 * nextInt(n) is Math.floor(nextFloat() * n), which is not rejection-sampled:
 * for n above 2^21 the product can round up to n, so the result is clamped to
 * n - 1. For the small ranges the tests use (n <= 2^21) the product is exact
 * enough that no clamping ever happens and the distribution is uniform up to
 * the 2^-32 resolution of nextFloat().
 */
(function (global) {
  'use strict';

  function mulberry32(seed) {
    var a = seed | 0;

    function nextU32() {
      a = (a + 0x6D2B79F5) | 0;
      var t = Math.imul(a ^ (a >>> 15), 1 | a);
      t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
      return (t ^ (t >>> 14)) >>> 0;
    }

    function nextFloat() {
      return nextU32() / 4294967296;
    }

    function nextInt(n) {
      if (!Number.isInteger(n) || n < 1 || n > 4294967296) {
        throw new RangeError('nextInt(n) needs an integer 1 <= n <= 2^32, got ' + n);
      }
      var v = Math.floor(nextFloat() * n);
      return v >= n ? n - 1 : v;
    }

    return { nextU32: nextU32, nextInt: nextInt, nextFloat: nextFloat };
  }

  global.mulberry32 = mulberry32;
})(globalThis);
