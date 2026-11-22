/* Dedicated worker for selftest.js (test-only).
 *
 * Answers every message with {echo: <the message>, delayed: <ms>, measuredMs}.
 * A message {delay: N} is answered after a timer of N ms that runs inside the
 * worker; measuredMs is then read from the worker's own performance.now(), so
 * it shows that the worker's timer ran in real time.
 */
'use strict';

self.onmessage = function (ev) {
  var msg = ev.data;
  var t0 = performance.now();
  var delay = msg && typeof msg.delay === 'number' ? msg.delay : 0;

  function reply() {
    self.postMessage({ echo: msg, delayed: delay, measuredMs: performance.now() - t0 });
  }

  if (delay > 0) setTimeout(reply, delay);
  else reply();
};
