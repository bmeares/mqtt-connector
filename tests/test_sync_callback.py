#! /usr/bin/env python3
"""A failing `pipe.sync()` must not escape the MQTT message callback.

Regression test for a 2026-07-25 outage: a restarted database left a stale
pooled connection, `pipe.sync()` raised inside the paho callback thread, and the
`sync pipes --loop` job stopped ingesting for 11.5 hours while still reporting
"running". `_syncing_pipes` blocks re-subscription and a long `--min-seconds`
means the outer loop never retries, so one exception ended ingest until someone
restarted the job by hand.

Run: python -m pytest tests/ -q   (or: python tests/test_sync_callback.py)
"""
import sys
from pathlib import Path

### Import `_sync` as a top-level module: the plugin directory is named
### `mqtt-connector`, which is not a valid package name, so importing through it
### fails on the relative imports in its `__init__.py`.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'plugins' / 'mqtt-connector'))

from _sync import _on_message_callback


class _RaisingPipe:
    """Stands in for a pipe whose instance connector just went away."""

    def __init__(self, exc):
        self._exc = exc
        self.calls = 0

    def sync(self, df, **kw):
        self.calls += 1
        raise self._exc

    def __str__(self):
        return "Pipe('mqtt:test', 'test', 'bytes')"


def _feed(pipe, times=1, payload=None, num_docs_ref=None):
    for _ in range(times):
        _on_message_callback(
            payload={'ts': 1, 'value': 2} if payload is None else payload,
            pipe=pipe,
            payload_parser=None,
            sync_kwargs={},
            num_docs_ref=[0] if num_docs_ref is None else num_docs_ref,
            topic='sensors/abc/heartbeat',
        )


def test_sync_failure_does_not_propagate():
    pipe = _RaisingPipe(RuntimeError('terminating connection due to administrator command'))
    _feed(pipe)
    assert pipe.calls == 1, 'the callback should still attempt the sync'


def test_every_later_message_retries():
    """Self-healing depends on the next message trying again, not on a retry loop."""
    pipe = _RaisingPipe(RuntimeError('connection already closed'))
    ref = [0]
    _feed(pipe, times=3, num_docs_ref=ref)
    assert pipe.calls == 3, f'every message should retry; got {pipe.calls}'


def test_successful_sync_still_reports():
    """The guard must not swallow the normal path."""
    class _OkPipe(_RaisingPipe):
        def sync(self, df, **kw):
            self.calls += 1
            return True, f'Synced {len(df)} rows.'

    pipe = _OkPipe(None)
    _feed(pipe)
    assert pipe.calls == 1


if __name__ == '__main__':
    test_sync_failure_does_not_propagate()
    test_every_later_message_retries()
    test_successful_sync_still_reports()
    print('ok')
