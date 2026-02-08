#!/usr/bin/env python3
"""Tests for comment staleness detection and remolt context system in index.html."""
import re
import os
import json
import sys

PASS = 0
FAIL = 0

def test(name, condition):
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"  ✅ {name}")
    else:
        FAIL += 1
        print(f"  ❌ {name}")

def main():
    global PASS, FAIL
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    html_path = os.path.join(root, 'index.html')
    
    with open(html_path, 'r') as f:
        html = f.read()

    print("\n🧪 Comment Staleness Detection Tests\n")

    # === SYNTAX TESTS ===
    print("--- Syntax & Structure ---")
    test("Brace balance", html.count('{') == html.count('}'))
    test("Paren balance", html.count('(') == html.count(')'))
    test("Bracket balance", html.count('[') == html.count(']'))
    test("DOCTYPE present", '<!DOCTYPE html>' in html)
    test("Closing </html>", '</html>' in html)
    test("Closing </script>", '</script>' in html)

    # === FUNCTION EXISTENCE ===
    print("\n--- Core Functions ---")
    test("checkCommentStaleness defined", 'function checkCommentStaleness(' in html)
    test("buildRemoltContext defined", 'function buildRemoltContext(' in html)
    test("renderRemoltBanner defined", 'function renderRemoltBanner(' in html)
    test("markStaleComments defined", 'function markStaleComments(' in html)
    test("copyRemoltContext defined", 'function copyRemoltContext(' in html)
    test("maybePostRemoltRecommendation defined", 'function maybePostRemoltRecommendation(' in html)

    # === UI ELEMENTS ===
    print("\n--- Modal UI Elements ---")
    test("health-badge in modal", 'id="health-badge"' in html)
    test("error-panel in modal", 'id="error-panel"' in html)
    test("agent-play-btn in modal", 'id="agent-play-btn"' in html)
    test("agent-stop-btn in modal", 'id="agent-stop-btn"' in html)
    test("agent-status in modal", 'id="agent-status"' in html)
    test("remolt-banner in modal", 'id="remolt-banner"' in html)

    # === WINDOW EXPORTS ===
    print("\n--- Global Function Exports ---")
    test("startAgentPlay exported to window", 'window.startAgentPlay=startAgentPlay' in html)
    test("stopAgentPlay exported to window", 'window.stopAgentPlay=stopAgentPlay' in html)
    test("copyRemoltContext exported to window", 'window.copyRemoltContext=copyRemoltContext' in html)

    # === STALENESS DETECTION LOGIC ===
    print("\n--- Staleness Detection Logic ---")
    test("BUG_KEYWORDS regex defined", 'BUG_KEYWORDS=' in html)
    test("STALE_THRESHOLD defined", 'STALE_THRESHOLD=' in html)
    test("Version mismatch detection", 'c.version<gen' in html or 'c.version&&c.version<gen' in html)
    test("Bug keyword matching", 'crash' in html and 'broken' in html and 'unplayable' in html)
    test("localStorage staleness storage", 'rappterzoo-staleness' in html)
    test("Deduplication check for remolt recommendations", 'alreadyPosted' in html)

    # === REMOLT CONTEXT BUILDER ===
    print("\n--- Remolt Context Builder ---")
    test("Temporal data section", "'temporal'" in html or 'temporal:' in html)
    test("Situational data section", "'situational'" in html or 'situational:' in html)
    test("commentSignals section", "'commentSignals'" in html or 'commentSignals:' in html)
    test("remoltGuidance section", "'remoltGuidance'" in html or 'remoltGuidance:' in html)
    test("Error frequency calculation", 'errorFrequency' in html)
    test("Health status classification", "'healthy'" in html or "healthy" in html)
    test("Bug reports collected", 'bugReports' in html)
    test("Feature requests collected", 'featureRequests' in html)

    # === CSS CLASSES ===
    print("\n--- CSS Styles ---")
    test("Stale comment CSS", '.comment.stale' in html)
    test("Remolt banner CSS", '.remolt-banner' in html)
    test("Needs-remolt badge CSS", '.needs-remolt-badge' in html)
    test("Health badge CSS", '.health-badge' in html)
    test("Error panel CSS", '.error-panel' in html)

    # === AGENT PLAYER ===
    print("\n--- Agent Player ---")
    test("AgentPlayer class defined", 'function AgentPlayer(' in html)
    test("Agent play start function", 'function startAgentPlay(' in html)
    test("Agent play stop function", 'function stopAgentPlay(' in html)
    test("Agent play button toggling", "playBtn.style.display='none'" in html or 'playBtn)playBtn.style.display' in html)
    test("Stop button toggling", "stopBtn.style.display=''" in html or 'stopBtn)stopBtn.style.display' in html)
    test("closeModal stops agent", 'stopAgentPlay()' in html and 'closeModal' in html)

    # === BRIDGE ===
    print("\n--- Game Bridge ---")
    test("bridgeScript defined", 'bridgeScript' in html)
    test("rappterzoo-error listener", "rappterzoo-error" in html)
    test("rappterzoo-heartbeat listener", "rappterzoo-heartbeat" in html)
    test("rappterzoo-reply listener", "rappterzoo-reply" in html)
    test("onerror hook in bridge", 'window.onerror' in html)
    test("unhandledrejection hook", 'unhandledrejection' in html)

    # === COMMENT VERSION TRACKING ===
    print("\n--- Comment Version Tracking ---")
    test("New comments get version", "version:Math.max(1,app.gen)" in html)
    test("Version badge in comment rendering", "vTag=c.version" in html)
    test("HealthBot remolt comment includes context JSON", 'Context for next molt' in html)

    # === INTEGRATION ===
    print("\n--- Integration ---")
    test("checkCommentStaleness called in openDetail", 'checkCommentStaleness(app)' in html)
    test("updateHealthBadge called in openDetail", re.search(r'renderComments\(app\);\s*\n\s*updateHealthBadge\(\)', html) is not None)
    test("renderErrorPanel called in openDetail", 'renderErrorPanel()' in html)
    test("renderRecPanel called in openDetail", 'renderRecPanel()' in html)

    # === GAMEPLAY RECORDER ===
    print("\n--- Gameplay Recorder ---")
    test("startRecording defined", 'function startRecording(' in html)
    test("stopRecording defined", 'function stopRecording(' in html)
    test("finishRecording defined", 'function finishRecording(' in html)
    test("renderRecPanel defined", 'function renderRecPanel(' in html)
    test("updateRecordUI defined", 'function updateRecordUI(' in html)
    test("updateRecordCounter defined", 'function updateRecordCounter(' in html)
    test("exportRecording defined", 'function exportRecording(' in html)
    test("exportAllRecordings defined", 'function exportAllRecordings(' in html)
    test("importRecording defined", 'function importRecording(' in html)
    test("deleteRecording defined", 'function deleteRecording(' in html)
    test("replayRecording defined", 'function replayRecording(' in html)
    test("startScriptedAgentPlay defined", 'function startScriptedAgentPlay(' in html)
    test("toggleRecPanel defined", 'function toggleRecPanel(' in html)

    # === RECORDER UI ===
    print("\n--- Recorder UI Elements ---")
    test("Record button in modal", 'id="rec-btn"' in html)
    test("Stop Record button in modal", 'id="rec-stop-btn"' in html)
    test("Record counter in modal", 'id="rec-counter"' in html)
    test("Recording panel div in modal", 'id="rec-panel"' in html)
    test("Import button in modal", 'importRecording()' in html)

    # === RECORDER WINDOW EXPORTS ===
    print("\n--- Recorder Window Exports ---")
    test("startRecording exported", 'window.startRecording=startRecording' in html)
    test("stopRecording exported", 'window.stopRecording=stopRecording' in html)
    test("importRecording exported", 'window.importRecording=importRecording' in html)
    test("exportRecording exported", 'window.exportRecording=exportRecording' in html)
    test("replayRecording exported", 'window.replayRecording=replayRecording' in html)
    test("deleteRecording exported", 'window.deleteRecording=deleteRecording' in html)
    test("toggleRecPanel exported", 'window.toggleRecPanel=toggleRecPanel' in html)

    # === BRIDGE INPUT FORWARDING ===
    print("\n--- Bridge Input Forwarding ---")
    test("keydown forwarded from iframe", 'rappterzoo-input' in html)
    test("keydown event listener in bridge", 'document.addEventListener("keydown"' in html or "document.addEventListener('keydown'" in html or 'addEventListener(\\"keydown\\"' in html)
    test("mousedown event listener in bridge", 'mousedown' in html)
    test("Input kind:key in bridge", "kind:\\'key\\'" in html or 'kind:"key"' in html or "kind:'key'" in html)

    # === REAL DOM EVENT INJECTION ===
    print("\n--- Real DOM Event Injection ---")
    test("dispatchInput command in bridge", 'cmd==="dispatchInput"' in html)
    test("KeyboardEvent dispatched", 'new KeyboardEvent("keydown"' in html)
    test("KeyboardEvent keyup dispatched", 'new KeyboardEvent("keyup"' in html)
    test("MouseEvent mousedown dispatched", 'new MouseEvent("mousedown"' in html)
    test("MouseEvent click dispatched", 'new MouseEvent("click"' in html)
    test("MouseEvent mousemove dispatched", 'new MouseEvent("mousemove"' in html)
    test("Canvas targeted for events", 'document.querySelector("canvas")' in html)
    test("elementFromPoint for click targeting", 'document.elementFromPoint' in html)
    test("dispatchInput used in AgentPlayer loop", "sendCmd('dispatchInput'" in html)
    test("dispatchInput used in scripted replay", "sendCmd('dispatchInput',{input:step})" in html)
    test("Key mapping for agent play", 'keyMap=' in html)
    test("ArrowLeft in key mapping", "left:'ArrowLeft'" in html)

    # === RECORDER STORAGE ===
    print("\n--- Recorder Storage ---")
    test("localStorage key for recordings", 'rappterzoo-recordings' in html)
    test("getRecordings function", 'function getRecordings(' in html)
    test("saveRecordings function", 'function saveRecordings(' in html)
    test("State snapshots captured", 'stateSnapshots' in html)
    test("Max 10 recordings per app", 'all[stem].length>10' in html)

    # === SCRIPTED REPLAY ===
    print("\n--- Scripted Agent Replay ---")
    test("Scripted replay replays key inputs", "step.kind==='key'" in html)
    test("Scripted replay replays clicks", "step.kind==='click'" in html)
    test("Adaptive mode after script exhaustion", 'Adapting' in html)
    test("Posts comment after scripted replay", 'Scripted Replay Session' in html)

    # === RECORDER CSS ===
    print("\n--- Recorder CSS ---")
    test("Recording panel CSS", '.rec-panel' in html)
    test("Recording entry CSS", '.rec-entry' in html)
    test("Record pulse animation", '@keyframes rec-pulse' in html)
    test("Recording panel body CSS", '.rec-panel-body' in html)

    # === CLOSE MODAL STOPS RECORDING ===
    print("\n--- Recording Lifecycle ---")
    test("closeModal stops recording", 'stopRecording()' in html and 'closeModal' in html)
    test("Periodic state snapshots", 'steps.length%50===0' in html)

    # === MANIFEST SYNC ===
    print("\n--- Manifest Exists ---")
    manifest_path = os.path.join(root, 'apps', 'manifest.json')
    test("manifest.json exists", os.path.exists(manifest_path))
    if os.path.exists(manifest_path):
        with open(manifest_path) as f:
            manifest = json.load(f)
        test("manifest has categories", 'categories' in manifest)
        test("manifest has meta", 'meta' in manifest)

    print(f"\n{'='*40}")
    print(f"Results: {PASS} passed, {FAIL} failed, {PASS+FAIL} total")
    if FAIL > 0:
        print("❌ SOME TESTS FAILED")
        sys.exit(1)
    else:
        print("✅ ALL TESTS PASSED")
        sys.exit(0)

if __name__ == '__main__':
    main()
