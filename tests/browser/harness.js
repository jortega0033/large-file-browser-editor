/* Check collector and reporter for the browser harness pages (test-only).
 *
 * Classic script for pages (it uses the DOM). Set the suite name on the page:
 *   <html lang="en" data-suite="selftest">
 *
 *   check(name, ok, detail, options)  record one assertion; options.realtime
 *                                     marks a check on elapsed real time
 *   measure(name, value, unit)        record a number that is not asserted
 *   done()                            finish: render, set data-harness, and
 *                                     POST the report when the URL has run=...
 *   serverNow()                       Promise<number>: GET /tests/browser/now
 *   urlParam(name)                    query parameter value or null
 *
 * Report: {suite, run?, passed, failed, checks, measurements, env, truncated?}
 * It is written into <pre id="report"> and, with run=<token> in the page URL,
 * sent to POST /tests/browser/report with the token in the field "run".
 * Without run= (a manual run) nothing is sent.
 *
 * With vt=1 in the URL (virtual-time fallback) a check declared
 * {realtime: true} is written to measurements as {name, value, asserted:
 * false} and counts neither as passed nor as failed.
 *
 * User-visible text is set only through textContent; positions and colours
 * only through element.style (the page runs under a CSP without inline style).
 */
(function (global) {
  'use strict';

  var doc = global.document;
  var root = doc.documentElement;
  var REPORT_URL = '/tests/browser/report';
  var NOW_URL = '/tests/browser/now';
  var MAX_REPORT_BYTES = 900 * 1024; // the server cap is 1 MiB
  var MAX_AUTO_ERRORS = 50;
  var MAX_DETAIL = 4000;

  var checks = [];
  var measurements = [];
  var finished = false;
  var donePromise = null;
  var autoErrors = 0;
  var suppressedErrors = 0;
  var ui = null;

  function urlParam(name) {
    return new URLSearchParams(global.location.search).get(name);
  }

  var vt = urlParam('vt') === '1';
  var token = urlParam('run');
  var suite = root.dataset.suite || 'unknown';

  function formatDetail(detail) {
    if (detail === undefined || detail === null) return '';
    var s;
    if (typeof detail === 'string') s = detail;
    else if (typeof detail === 'number' || typeof detail === 'boolean') s = String(detail);
    else {
      try { s = JSON.stringify(detail); } catch (e) { s = String(detail); }
    }
    return s.length > MAX_DETAIL ? s.slice(0, MAX_DETAIL) + '...' : s;
  }

  function jsonValue(value) {
    if (typeof value === 'string' || typeof value === 'boolean' || value === null) return value;
    if (typeof value === 'number') return Number.isFinite(value) ? value : String(value);
    return formatDetail(value);
  }

  // ---- page rendering (textContent and element.style only) ----

  function ensureUi() {
    if (ui || !doc.body) return ui;
    var main = doc.createElement('main');
    main.id = 'harness-results';
    main.style.fontFamily = 'system-ui, sans-serif';
    main.style.padding = '16px';
    main.style.maxWidth = '100%';
    main.style.boxSizing = 'border-box';
    main.style.color = '#1a1a1a';
    main.style.background = '#ffffff';

    var h1 = doc.createElement('h1');
    h1.style.fontSize = '1.25rem';
    h1.textContent = 'Browser harness: suite ' + suite;
    main.appendChild(h1);

    var summary = doc.createElement('p');
    summary.setAttribute('role', 'status');
    summary.style.fontWeight = '600';
    summary.textContent = 'Running...';
    main.appendChild(summary);

    var list = doc.createElement('ul');
    list.setAttribute('aria-label', 'Checks');
    list.style.paddingLeft = '1.25rem';
    list.style.overflowWrap = 'anywhere';
    main.appendChild(list);

    var mHeading = doc.createElement('h2');
    mHeading.style.fontSize = '1rem';
    mHeading.textContent = 'Measurements';
    main.appendChild(mHeading);

    var mList = doc.createElement('ul');
    mList.setAttribute('aria-label', 'Measurements');
    mList.style.paddingLeft = '1.25rem';
    mList.style.overflowWrap = 'anywhere';
    main.appendChild(mList);

    var rHeading = doc.createElement('h2');
    rHeading.style.fontSize = '1rem';
    rHeading.textContent = 'Report (JSON)';
    main.appendChild(rHeading);

    var pre = doc.getElementById('report');
    if (!pre) {
      pre = doc.createElement('pre');
      pre.id = 'report';
    }
    pre.style.whiteSpace = 'pre-wrap';
    pre.style.overflowWrap = 'anywhere';
    pre.style.maxHeight = '40vh';
    pre.style.overflow = 'auto';
    pre.style.border = '1px solid #767676';
    pre.style.padding = '8px';
    pre.style.fontSize = '0.8125rem';
    if (!pre.textContent) pre.textContent = '(written when done() is called)';
    main.appendChild(pre);

    doc.body.appendChild(main);
    ui = { summary: summary, list: list, mList: mList, pre: pre };
    for (var i = 0; i < checks.length; i++) addCheckItem(checks[i]);
    for (var j = 0; j < measurements.length; j++) addMeasurementItem(measurements[j]);
    updateSummary();
    return ui;
  }

  function addCheckItem(entry) {
    if (!ui) return;
    var li = doc.createElement('li');
    li.style.color = entry.ok ? '#0a5c1e' : '#a00000';
    var text = (entry.ok ? 'PASS ' : 'FAIL ') + entry.name;
    if (entry.detail) text += ' - ' + entry.detail;
    if (entry.realtime) text += ' [realtime]';
    li.textContent = text;
    ui.list.appendChild(li);
  }

  function addMeasurementItem(m) {
    if (!ui) return;
    var li = doc.createElement('li');
    var text = m.name + ': ' + m.value + (m.unit ? ' ' + m.unit : '');
    if (m.asserted === false) text += ' (virtual time, not asserted)';
    li.textContent = text;
    ui.mList.appendChild(li);
  }

  function counts() {
    var passed = 0;
    for (var i = 0; i < checks.length; i++) if (checks[i].ok) passed++;
    return { passed: passed, failed: checks.length - passed };
  }

  function updateSummary() {
    if (!ui) return;
    var c = counts();
    var text = c.passed + ' passed, ' + c.failed + ' failed';
    if (finished) text = (c.failed === 0 ? 'Done: ' : 'Failed: ') + text;
    else text = 'Running: ' + text;
    ui.summary.textContent = text;
    ui.summary.style.color = finished && c.failed > 0 ? '#a00000' : '#1a1a1a';
  }

  // ---- recording ----

  function check(name, ok, detail, options) {
    var opts = options || {};
    var pass = !!ok;
    if (finished) {
      if (global.console) global.console.warn('check after done() ignored: ' + name);
      return pass;
    }
    if (opts.realtime === true && vt) {
      var m = {
        name: String(name),
        value: detail !== undefined ? jsonValue(detail) : pass,
        asserted: false
      };
      measurements.push(m);
      addMeasurementItem(m);
      return pass;
    }
    var entry = { name: String(name), ok: pass, detail: formatDetail(detail) };
    if (opts.realtime === true) entry.realtime = true;
    checks.push(entry);
    addCheckItem(entry);
    updateSummary();
    return pass;
  }

  function measure(name, value, unit) {
    if (finished) {
      if (global.console) global.console.warn('measure after done() ignored: ' + name);
      return;
    }
    var m = { name: String(name), value: jsonValue(value), unit: unit === undefined ? '' : String(unit) };
    measurements.push(m);
    addMeasurementItem(m);
  }

  // ---- uncaught errors become failed checks ----

  function autoFail(name, detail) {
    if (finished) return;
    if (autoErrors >= MAX_AUTO_ERRORS) {
      suppressedErrors++;
      return;
    }
    autoErrors++;
    check(name, false, detail);
  }

  global.addEventListener('error', function (ev) {
    var target = ev.target;
    if (target && target !== global && target.tagName) {
      autoFail('resource failed to load: <' + target.tagName.toLowerCase() + '>',
        target.src || target.href || '');
      return;
    }
    var where = (ev.filename || '') + ':' + (ev.lineno || 0) + ':' + (ev.colno || 0);
    var stack = ev.error && ev.error.stack ? ' ' + ev.error.stack : '';
    autoFail('uncaught error: ' + (ev.message || 'unknown'), where + stack);
  }, true);

  global.addEventListener('unhandledrejection', function (ev) {
    var reason = ev.reason;
    var message = reason && reason.message ? reason.message : String(reason);
    var stack = reason && reason.stack ? reason.stack : '';
    autoFail('unhandled rejection: ' + message, stack);
  });

  // ---- report ----

  function envInfo() {
    return {
      userAgent: global.navigator.userAgent,
      hardwareConcurrency: global.navigator.hardwareConcurrency,
      vt: vt,
      origin: global.location.origin,
      timestamp: new Date().toISOString()
    };
  }

  function byteLength(text) {
    return new TextEncoder().encode(text).length;
  }

  // Returns the report object to render and send. A report over about 900 KiB
  // (the server cap is 1 MiB) is cut down: the checks list is replaced by the
  // failed checks only (the counts stay exact) and a "truncated" field says so.
  function fitReport(report) {
    if (byteLength(JSON.stringify(report)) <= MAX_REPORT_BYTES) return report;
    var failedOnly = report.checks.filter(function (c) { return !c.ok; }).slice(0, 100);
    var cut = {
      suite: report.suite,
      passed: report.passed,
      failed: report.failed,
      checks: failedOnly,
      measurements: report.measurements,
      env: report.env,
      truncated: 'report would exceed 1 MiB: checks list replaced by the counts ' +
        'and up to 100 failed checks (' + report.checks.length + ' checks recorded)'
    };
    if (report.run !== undefined) cut.run = report.run;
    if (byteLength(JSON.stringify(cut)) <= MAX_REPORT_BYTES) return cut;
    cut.measurements = report.measurements.slice(0, 100);
    cut.truncated += '; measurements cut to the first 100 of ' + report.measurements.length;
    if (byteLength(JSON.stringify(cut)) <= MAX_REPORT_BYTES) return cut;
    cut.checks = failedOnly.slice(0, 10).map(function (c) {
      return { name: c.name, ok: false, detail: '' };
    });
    return cut;
  }

  function buildReport() {
    var c = counts();
    var report = { suite: suite };
    if (token) report.run = token;
    report.passed = c.passed;
    report.failed = c.failed;
    report.checks = checks.slice();
    report.measurements = measurements.slice();
    report.env = envInfo();
    return report;
  }

  async function postReport(body) {
    var lastError = null;
    for (var attempt = 0; attempt < 2; attempt++) {
      try {
        var response = await global.fetch(REPORT_URL, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: body,
          cache: 'no-store'
        });
        if (response.ok) return;
        throw new Error('POST ' + REPORT_URL + ' answered ' + response.status);
      } catch (e) {
        lastError = e;
        if (e && /answered \d+/.test(String(e.message))) break; // an HTTP answer: do not retry
        await new Promise(function (resolve) { global.setTimeout(resolve, 300); });
      }
    }
    throw lastError;
  }

  function done() {
    if (donePromise) return donePromise;
    if (checks.length === 0) check('no checks were recorded', false, 'a suite must assert something');
    if (suppressedErrors > 0) {
      check('more uncaught errors were suppressed', false,
        suppressedErrors + ' errors beyond the first ' + MAX_AUTO_ERRORS);
    }
    finished = true;
    var report = fitReport(buildReport());
    var allPassed = report.failed === 0;
    root.dataset.harness = allPassed ? 'done' : 'failed';
    root.dataset.harnessPost = token ? 'pending' : 'none';
    doc.title = (allPassed ? 'PASS ' : 'FAIL ') + suite;

    var text = JSON.stringify(report, null, 2);
    var render = function () {
      if (!ensureUi()) return;
      ui.pre.textContent = text;
      updateSummary();
    };
    if (doc.body) render();
    else doc.addEventListener('DOMContentLoaded', render);

    if (!token) {
      donePromise = Promise.resolve(report);
      return donePromise;
    }
    donePromise = postReport(JSON.stringify(report)).then(function () {
      root.dataset.harnessPost = 'sent';
      return report;
    }, function (e) {
      root.dataset.harnessPost = 'failed';
      if (global.console) global.console.error('report not delivered: ' + (e && e.message));
      return report;
    });
    return donePromise;
  }

  async function serverNow() {
    var response = await global.fetch(NOW_URL, { cache: 'no-store' });
    if (!response.ok) throw new Error('GET ' + NOW_URL + ' answered ' + response.status);
    var value = await response.json();
    if (typeof value !== 'number' || !Number.isFinite(value)) {
      throw new Error('GET ' + NOW_URL + ' did not return a number');
    }
    return value;
  }

  if (doc.readyState === 'loading') doc.addEventListener('DOMContentLoaded', ensureUi);
  else ensureUi();

  global.check = check;
  global.measure = measure;
  global.done = done;
  global.serverNow = serverNow;
  global.urlParam = urlParam;
})(window);
