/* The harness checks itself (test-only).
 *
 * Query parameters: fail=1 adds a deliberately failing check, hang=1 never
 * calls done(), slow=1 calls done() only after a further 3 s page timer,
 * vt=1 turns the {realtime: true} checks into measurements (see harness.js),
 * run=<token> makes done() send the report (set by the runner).
 */
(function () {
  'use strict';

  var PRNG_PINS = [
    [7, [50271532, 266108690, 4195786334]],
    [99, [1118692146, 3456687457, 2323025554]],
    [1337, [792042790, 815997621, 3480950701]],
    [2024, [3486492848, 3052955074, 2793987405]]
  ];

  var LINE_PINS = [
    [1, '2026-01-01T00:00:00Z service-1 INFO event=001 value=37'],
    [10, '2026-01-01T00:00:09Z service-2 WARN event=010 value=67'],
    [25, '2026-01-01T00:00:24Z service-1 ERROR event=025 value=16'],
    [200, '2026-01-01T00:03:19Z service-0 ERROR event=200 value=27'],
    [500000, '2026-01-01T138:53:19Z service-0 ERROR event=500000 value=32'],
    [1000000, '2026-01-01T277:46:39Z service-0 ERROR event=1000000 value=64']
  ];

  var FIXTURES = [
    { label: 'LF 10,000 lines', lines: 10000, opts: { eol: 'lf' }, bytes: 558511,
      sha: '83ea4b136fe6da1f75a1d1939d51f7011551e83d8030352ec1bc35958b24b2a7' },
    { label: 'LF 1,000,000 lines', lines: 1000000, opts: { eol: 'lf' }, bytes: 58479896,
      sha: '8da2445b134557e3f11bf9e748d6101b8456a9b71a60fe9731d6559c4151d508' },
    { label: 'CRLF 1,000,000 lines', lines: 1000000, opts: { eol: 'crlf' }, bytes: 59479896,
      sha: '00d1765a3a2f2ecf0a74f3b2191ceaac0e2d9da21451d3ff33f05c52f6882184' },
    { label: 'BOM + LF 1,000,000 lines', lines: 1000000, opts: { eol: 'lf', bom: true }, bytes: 58479899,
      sha: '5660454d10627ac968f6eedfc618f2c04bd87ed673d567e352340296b2257410' },
    { label: 'mixed seed 7, 10,000 lines', lines: 10000, opts: { eol: 'mixed', seed: 7 }, bytes: 563529,
      sha: 'df6acdf8d463b2702b0e6c0f853087aa96c64c4a2f819b7fc36082bf698e329c' }
  ];

  var MAX_CHUNK_UNITS = 1048576;

  function sleep(ms) {
    return new Promise(function (resolve) { setTimeout(resolve, ms); });
  }

  function errText(e) {
    return String(e && e.stack ? e.stack : e);
  }

  async function guarded(label, fn) {
    try {
      await fn();
    } catch (e) {
      check(label + ' threw', false, errText(e));
    }
  }

  function askWorker(message, timeoutMs) {
    return new Promise(function (resolve, reject) {
      var w = new Worker('echo_worker.js');
      var timer = setTimeout(function () {
        w.terminate();
        reject(new Error('worker did not answer within ' + timeoutMs + ' ms'));
      }, timeoutMs);
      w.onmessage = function (ev) {
        clearTimeout(timer);
        w.terminate();
        resolve(ev.data);
      };
      w.onerror = function (ev) {
        clearTimeout(timer);
        w.terminate();
        reject(new Error('worker error: ' + (ev.message || 'failed to start')));
      };
      w.postMessage(message);
    });
  }

  function waitFor(predicate, timeoutMs) {
    return new Promise(function (resolve) {
      var start = performance.now();
      (function poll() {
        var value = predicate();
        if (value || performance.now() - start >= timeoutMs) resolve(value);
        else setTimeout(poll, 10);
      })();
    });
  }

  // ---- checks that prove the wait strategy (real time) ----

  async function realtimeChecks() {
    await guarded('page timer against server clock', async function () {
      var before = await serverNow();
      await sleep(300);
      var after = await serverNow();
      var delta = after - before;
      check('server clock advances across a 300 ms page timer', delta >= 290,
        'server clock advanced ' + delta.toFixed(1) + ' ms (needs >= 290)', { realtime: true });
    });

    await guarded('worker timer', async function () {
      var reply = await askWorker({ delay: 200 }, 10000);
      var measured = reply.measuredMs;
      check('worker answers after its own 200 ms timer', measured >= 190,
        'worker measured ' + measured.toFixed(1) + ' ms (needs >= 190)', { realtime: true });
    });
  }

  // ---- generator ----

  function prngChecks() {
    PRNG_PINS.forEach(function (pin) {
      var rng = mulberry32(pin[0]);
      var got = [rng.nextU32(), rng.nextU32(), rng.nextU32()];
      check('mulberry32 seed ' + pin[0] + ' first three outputs',
        got.join(',') === pin[1].join(','), got.join(', ') + ' (expected ' + pin[1].join(', ') + ')');
    });

    var a = mulberry32(7);
    var b = mulberry32(7);
    var same = true;
    for (var i = 0; i < 100; i++) if (a.nextU32() !== b.nextU32()) same = false;
    check('same seed gives the same sequence', same);
    check('different seeds give different sequences',
      mulberry32(7).nextU32() !== mulberry32(8).nextU32());

    var rng = mulberry32(2024);
    var floatsOk = true;
    var floatMin = 1;
    var floatMax = 0;
    for (var f = 0; f < 10000; f++) {
      var x = rng.nextFloat();
      if (!(x >= 0 && x < 1)) floatsOk = false;
      if (x < floatMin) floatMin = x;
      if (x > floatMax) floatMax = x;
    }
    check('nextFloat is in [0, 1)', floatsOk,
      '10,000 draws, min ' + floatMin.toFixed(5) + ', max ' + floatMax.toFixed(5));

    [1, 2, 3, 10, 1000].forEach(function (n) {
      var r = mulberry32(1337);
      var ok = true;
      var seen = {};
      for (var k = 0; k < 5000; k++) {
        var v = r.nextInt(n);
        if (!Number.isInteger(v) || v < 0 || v >= n) ok = false;
        seen[v] = true;
      }
      var distinct = Object.keys(seen).length;
      var expectAll = n <= 10; // 5000 draws reach every value of a small range
      check('nextInt(' + n + ') is an integer in [0, ' + n + ')', ok && (!expectAll || distinct === n),
        distinct + ' distinct values in 5000 draws');
    });

    var threw = 0;
    [0, -1, 1.5, NaN].forEach(function (bad) {
      try { mulberry32(1).nextInt(bad); } catch (e) { if (e instanceof RangeError) threw++; }
    });
    check('nextInt rejects 0, -1, 1.5 and NaN with RangeError', threw === 4, threw + ' of 4 threw');
  }

  // ---- fixture lines ----

  function fixtureLineChecks() {
    LINE_PINS.forEach(function (pin) {
      var got = fixtureLine(pin[0]);
      check('fixtureLine(' + pin[0] + ')', got === pin[1], got);
    });
    var threw = 0;
    [0, -3, 1.5].forEach(function (bad) {
      try { fixtureLine(bad); } catch (e) { if (e instanceof RangeError) threw++; }
    });
    check('fixtureLine rejects 0, -3 and 1.5 with RangeError', threw === 3, threw + ' of 3 threw');
  }

  async function smallFixtureChecks() {
    var enc = new TextEncoder();

    var bomChunks = fixtureChunks(3, { eol: 'lf', bom: true });
    var head = Array.from(enc.encode(bomChunks[0].slice(0, 1)));
    check('bom:true starts with U+FEFF, encoded as EF BB BF',
      bomChunks[0].charCodeAt(0) === 0xFEFF && head.join(',') === '239,187,191',
      head.map(function (b) { return b.toString(16); }).join(' '));
    var plain = fixtureChunks(3, { eol: 'lf' });
    check('without bom the first character is the line text', plain[0].charCodeAt(0) === 0x32);

    var crlf = fixtureChunks(5, { eol: 'crlf' }).join('');
    check('crlf: every line ends with CRLF, the last one too',
      crlf.endsWith('\r\n') && crlf.split('\r\n').length === 6 && crlf.indexOf('\n') === crlf.indexOf('\r\n') + 1);
    var lf = fixtureChunks(5, { eol: 'lf' }).join('');
    check('lf: every line ends with LF, the last one too',
      lf.endsWith('\n') && lf.indexOf('\r') === -1 && lf.split('\n').length === 6);
    check('zero lines give no chunks', fixtureChunks(0).length === 0);

    var mixed = fixtureChunks(10000, { eol: 'mixed', seed: 7 }).join('');
    var lines = mixed.split('\n');
    var rng = mulberry32(7);
    var ruleOk = true;
    for (var i = 0; i < 2000; i++) {
      var expectCr = (rng.nextU32() & 1) === 1;
      if (lines[i].endsWith('\r') !== expectCr) ruleOk = false;
    }
    var crCount = mixed.split('\r\n').length - 1;
    check('mixed: line i ends with CRLF when the i-th mulberry32 output is odd (first 2000 lines)',
      ruleOk && crCount > 0 && crCount < 10000, crCount + ' of 10,000 lines end with CRLF');

    var one = await digestChunks([]);
    check('sha256 of no chunks is the empty-input digest',
      one.sha256 === 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855' && one.bytes === 0);
  }

  async function sampleCheck() {
    var response = await fetch('/api/v1/sample');
    var sample = await response.json();
    var text = fixtureChunks(200, { eol: 'lf' }).join('');
    var bytes = new TextEncoder().encode(sample.text).length;
    check('200-line LF fixture equals GET /api/v1/sample text', response.ok && text === sample.text,
      'status ' + response.status + ', fixture ' + text.length + ' chars, sample ' + sample.text.length + ' chars');
    check('GET /api/v1/sample text is 10,991 bytes', bytes === 10991, bytes + ' bytes');
  }

  async function fixtureHashChecks() {
    for (var k = 0; k < FIXTURES.length; k++) {
      var fx = FIXTURES[k];
      await guarded(fx.label, async function () {
        var t0 = performance.now();
        var chunks = fixtureChunks(fx.lines, fx.opts);
        var t1 = performance.now();
        var longest = 0;
        for (var c = 0; c < chunks.length; c++) if (chunks[c].length > longest) longest = chunks[c].length;
        var result = await digestChunks(chunks);
        var t2 = performance.now();
        check(fx.label + ': ' + fx.bytes + ' bytes',
          result.bytes === fx.bytes, result.bytes + ' bytes');
        check(fx.label + ': SHA-256', result.sha256 === fx.sha, result.sha256);
        check(fx.label + ': ' + chunks.length + ' chunks, none longer than 1 MiB',
          longest <= MAX_CHUNK_UNITS && (fx.lines < 100000 || chunks.length > 1),
          'longest chunk ' + longest + ' UTF-16 units');
        measure(fx.label + ': build chunks', Math.round(t1 - t0), 'ms');
        measure(fx.label + ': encode and hash', Math.round(t2 - t1), 'ms');
      });
      await sleep(0); // let the page paint between the heavy steps
    }
  }

  // ---- platform assumptions under the real CSP ----

  async function platformChecks() {
    await guarded('worker echo', async function () {
      var message = { hello: 'worker', list: [1, 2, 3] };
      var reply = await askWorker(message, 10000);
      check('dedicated worker from same-origin echo_worker.js answers an echo message',
        JSON.stringify(reply.echo) === JSON.stringify(message), JSON.stringify(reply.echo));
    });

    await guarded('element.style', function () {
      var box = document.createElement('div');
      box.style.position = 'relative';
      box.style.width = '100px';
      box.style.height = '100px';
      var child = document.createElement('div');
      child.style.position = 'absolute';
      child.style.top = '7px';
      child.style.left = '11px';
      child.style.width = '10px';
      child.style.height = '10px';
      box.appendChild(child);
      document.body.appendChild(box);
      var computed = getComputedStyle(child);
      check('a position set through element.style takes effect',
        computed.top === '7px' && child.offsetTop === 7 && child.offsetLeft === 11,
        'computed top ' + computed.top + ', offsetTop ' + child.offsetTop + ', offsetLeft ' + child.offsetLeft);
      child.style.transform = 'translateY(5px)';
      check('a transform set through element.style takes effect',
        getComputedStyle(child).transform === 'matrix(1, 0, 0, 1, 0, 5)', getComputedStyle(child).transform);
      box.remove();
    });

    await guarded('setAttribute style', async function () {
      var violation = null;
      var onViolation = function (ev) { violation = ev; };
      document.addEventListener('securitypolicyviolation', onViolation);
      var el = document.createElement('div');
      document.body.appendChild(el);
      el.setAttribute('style', 'top: 99px');
      var seen = await waitFor(function () { return violation; }, 2000);
      document.removeEventListener('securitypolicyviolation', onViolation);
      var directive = seen ? seen.violatedDirective + ' (effective ' + seen.effectiveDirective + ')' : 'none';
      check('setAttribute("style", ...) raises a securitypolicyviolation event for style-src',
        !!seen && String(seen.violatedDirective).indexOf('style-src') !== -1,
        'violatedDirective ' + directive + ', blockedURI ' + (seen ? seen.blockedURI : 'none'));
      check('setAttribute("style", ...) is blocked: the style is not applied',
        el.style.top === '' && getComputedStyle(el).top !== '99px',
        'el.style.top "' + el.style.top + '", computed top ' + getComputedStyle(el).top);
      el.remove();
    });

    await guarded('crypto.subtle', async function () {
      var available = typeof crypto !== 'undefined' && !!crypto.subtle &&
        typeof crypto.subtle.digest === 'function';
      var hex = '';
      if (available) {
        var d = await crypto.subtle.digest('SHA-256', new TextEncoder().encode('abc'));
        hex = Array.from(new Uint8Array(d), function (b) { return b.toString(16).padStart(2, '0'); }).join('');
      }
      check('crypto.subtle.digest is available and hashes "abc" correctly',
        hex === 'ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad',
        'isSecureContext ' + window.isSecureContext + ', available ' + available);
    });
  }

  // ---- main ----

  async function main() {
    var hang = urlParam('hang') === '1';
    var slow = urlParam('slow') === '1';

    if (urlParam('fail') === '1') {
      check('deliberate failure (fail=1)', false, 'requested by the fail=1 query parameter');
    }

    await guarded('real-time checks', realtimeChecks);
    await guarded('generator checks', prngChecks);
    await guarded('fixture line checks', fixtureLineChecks);
    await guarded('small fixture checks', smallFixtureChecks);
    await guarded('platform checks', platformChecks);
    await guarded('sample check', sampleCheck);
    await guarded('fixture hash checks', fixtureHashChecks);

    if (slow) {
      var t0 = performance.now();
      await sleep(3000);
      var waited = performance.now() - t0;
      check('slow=1: done() is called after a further 3 s page timer', waited >= 2990,
        'waited ' + waited.toFixed(1) + ' ms, page age ' + performance.now().toFixed(0) + ' ms (needs >= 2990)',
        { realtime: true });
    }

    if (hang) return; // never calls done(): the runner must time out
    await done();
  }

  main().catch(function (e) {
    check('selftest aborted', false, errText(e));
    if (urlParam('hang') !== '1') done();
  });
})();
