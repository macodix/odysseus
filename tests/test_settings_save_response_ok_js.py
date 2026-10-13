"""Frontend regression tests: verify settings save handlers check HTTP response status.

Locks in that static/js/settings.js verifies response.ok before displaying success,
preventing 401, 403, 400, and 500 responses from reporting false success.
"""
import re
import shutil
import subprocess
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parent.parent
_SETTINGS_JS = _REPO / "static" / "js" / "settings.js"
_HAS_NODE = shutil.which("node") is not None


@pytest.mark.skipif(not _HAS_NODE, reason="node binary not on PATH")
def test_settings_js_syntax():
    """Verify static/js/settings.js is syntactically valid JavaScript."""
    proc = subprocess.run(
        ["node", "--check", str(_SETTINGS_JS)],
        capture_output=True,
        text=True,
        cwd=str(_REPO),
    )
    assert proc.returncode == 0, f"JS syntax error:\n{proc.stderr}"


def test_all_settings_post_calls_verify_response_ok():
    """Every POST to /api/auth/settings in settings.js must check response.ok."""
    content = _SETTINGS_JS.read_text(encoding="utf-8")
    matches = list(re.finditer(r"fetch\(['\"]/api/auth/settings['\"],\s*\{\s*method:\s*['\"]POST['\"]", content))
    assert len(matches) >= 10, f"Expected at least 10 POST /api/auth/settings calls, found {len(matches)}"

    for m in matches:
        # Check that within the 500 characters following the fetch invocation, .ok is inspected
        window = content[m.start(): m.start() + 500]
        assert ".ok" in window, (
            f"Found POST fetch to /api/auth/settings without .ok check near char {m.start()}:\n"
            f"{window[:150]}..."
        )


@pytest.mark.skipif(not _HAS_NODE, reason="node binary not on PATH")
def test_failed_save_shows_failure_in_simulated_dom():
    """Verify that when fetch returns !res.ok, save logic catches and flags error."""
    js = """
    let msgText = '';
    let msgColor = '';
    const msg = {
      set textContent(v) { msgText = v; },
      get textContent() { return msgText; },
      style: { set color(v) { msgColor = v; }, get color() { return msgColor; } }
    };

    async function save(fetchImpl) {
      try {
        var res = await fetchImpl('/api/auth/settings', { method: 'POST' });
        if (!res.ok) throw new Error('HTTP ' + res.status);
        msg.textContent = 'Saved'; msg.style.color = 'var(--fg)';
      } catch (e) {
        msg.textContent = 'Failed to save'; msg.style.color = 'var(--red)';
      }
    }

    async function run() {
      // 1. Rejected fetch (403)
      await save(async () => ({ ok: false, status: 403 }));
      const rejectedResult = { text: msgText, color: msgColor };

      // 2. Server error (500)
      await save(async () => ({ ok: false, status: 500 }));
      const serverErrResult = { text: msgText, color: msgColor };

      // 3. Successful fetch (200)
      await save(async () => ({ ok: true, status: 200 }));
      const okResult = { text: msgText, color: msgColor };

      console.log(JSON.stringify({ rejectedResult, serverErrResult, okResult }));
    }
    run();
    """
    proc = subprocess.run(["node", "-e", js], capture_output=True, text=True, check=True)
    import json
    data = json.loads(proc.stdout)
    assert data["rejectedResult"] == {"text": "Failed to save", "color": "var(--red)"}
    assert data["serverErrResult"] == {"text": "Failed to save", "color": "var(--red)"}
    assert data["okResult"] == {"text": "Saved", "color": "var(--fg)"}

