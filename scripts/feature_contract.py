"""Feature Contract Extraction and Verification for Molt Pipeline.

Extracts a machine-readable "contract" of features from an HTML app before
molting, then verifies the contract is satisfied after the LLM rewrites it.
This prevents the cumulative information loss that occurs when LLMs do
full-file rewrites — subtle features (event listeners, tuned constants,
keyboard shortcuts) that exist in code but not in high-level descriptions
get silently dropped over generations.

Pure regex/parsing — no LLM dependency, runs in <100ms.
"""

import re
from typing import Optional


def extract_features(html: str) -> dict:
    """Extract a feature contract from HTML source.

    Returns a dict with categorized features found in the source code.
    Each feature has an 'id', 'type', and 'evidence' string that can be
    searched for in the post-molt output.
    """
    if not html or not html.strip():
        return {"features": [], "constants": {}, "summary": {}}

    features = []
    constants = {}

    # --- Event Listeners ---
    # addEventListener('click', ...) and on<event>="..." patterns
    listener_pattern = re.compile(
        r"""addEventListener\s*\(\s*['"](\w+)['"]""", re.IGNORECASE
    )
    for m in listener_pattern.finditer(html):
        event_type = m.group(1)
        fid = f"listener-{event_type}-{m.start()}"
        features.append({
            "id": fid,
            "type": "event_listener",
            "subtype": event_type,
            "evidence": f"addEventListener('{event_type}'",
            "line_hint": html[:m.start()].count('\n') + 1,
        })

    # Inline on<event> handlers on elements (deduplicated by event type)
    inline_handler_pattern = re.compile(
        r'<\w+[^>]+\bon(\w+)\s*=\s*["\']([^"\']{1,80})', re.IGNORECASE
    )
    seen_inline = set()
    for m in inline_handler_pattern.finditer(html):
        event_type = m.group(1).lower()
        handler = m.group(2).strip()
        key = (event_type, handler)
        if key not in seen_inline:
            seen_inline.add(key)
            features.append({
                "id": f"inline-handler-{event_type}-{len(seen_inline)}",
                "type": "inline_handler",
                "subtype": event_type,
                "evidence": f"on{event_type}=\"{handler[:40]}",
            })

    # --- localStorage Keys ---
    ls_get = re.compile(
        r"""localStorage\.(?:getItem|setItem|removeItem)\s*\(\s*['"]([^'"]+)['"]""",
    )
    ls_keys = set()
    for m in ls_get.finditer(html):
        ls_keys.add(m.group(1))
    for key in sorted(ls_keys):
        features.append({
            "id": f"localstorage-{key}",
            "type": "localstorage",
            "subtype": "key",
            "evidence": key,
        })

    # localStorage bracket access: localStorage['key'] or localStorage["key"]
    ls_bracket = re.compile(
        r"""localStorage\s*\[\s*['"]([^'"]+)['"]\s*\]"""
    )
    for m in ls_bracket.finditer(html):
        key = m.group(1)
        if key not in ls_keys:
            ls_keys.add(key)
            features.append({
                "id": f"localstorage-{key}",
                "type": "localstorage",
                "subtype": "key",
                "evidence": key,
            })

    # --- Animation Loops ---
    if re.search(r'requestAnimationFrame\s*\(', html):
        features.append({
            "id": "animation-raf",
            "type": "animation_loop",
            "subtype": "requestAnimationFrame",
            "evidence": "requestAnimationFrame(",
        })

    if re.search(r'setInterval\s*\(', html):
        features.append({
            "id": "animation-interval",
            "type": "animation_loop",
            "subtype": "setInterval",
            "evidence": "setInterval(",
        })

    # --- Canvas Operations ---
    if re.search(r'getContext\s*\(\s*[\'"]2d[\'"]\s*\)', html):
        features.append({
            "id": "canvas-2d",
            "type": "canvas",
            "subtype": "2d",
            "evidence": "getContext('2d')",
        })

    if re.search(r'getContext\s*\(\s*[\'"]webgl', html, re.IGNORECASE):
        features.append({
            "id": "canvas-webgl",
            "type": "canvas",
            "subtype": "webgl",
            "evidence": "getContext('webgl",
        })

    # --- Audio ---
    if re.search(r'AudioContext|webkitAudioContext', html):
        features.append({
            "id": "audio-context",
            "type": "audio",
            "subtype": "AudioContext",
            "evidence": "AudioContext",
        })

    if re.search(r'new\s+Audio\s*\(', html):
        features.append({
            "id": "audio-element",
            "type": "audio",
            "subtype": "Audio",
            "evidence": "new Audio(",
        })

    # --- Keyboard Shortcuts ---
    key_pattern = re.compile(
        r"""(?:e|event|ev|evt)\.(?:key|code|keyCode)\s*===?\s*['"]?(\w+)['"]?""",
        re.IGNORECASE,
    )
    seen_keys = set()
    for m in key_pattern.finditer(html):
        key = m.group(1)
        if key not in seen_keys:
            seen_keys.add(key)
            features.append({
                "id": f"keyboard-{key}",
                "type": "keyboard_shortcut",
                "subtype": key,
                "evidence": key,
            })

    # Also catch switch(e.key) { case 'x': patterns
    switch_key = re.compile(
        r"""case\s+['"](\w+)['"]\s*:""",
    )
    # Only include these if there's a keydown/keyup/keypress listener
    if re.search(r"key(?:down|up|press)", html, re.IGNORECASE):
        for m in switch_key.finditer(html):
            key = m.group(1)
            if key not in seen_keys and len(key) <= 20:
                seen_keys.add(key)
                features.append({
                    "id": f"keyboard-{key}",
                    "type": "keyboard_shortcut",
                    "subtype": key,
                    "evidence": key,
                })

    # --- CSS Animations / Transitions ---
    if re.search(r'@keyframes\s+(\w+)', html):
        for m in re.finditer(r'@keyframes\s+(\w+)', html):
            features.append({
                "id": f"css-animation-{m.group(1)}",
                "type": "css_animation",
                "subtype": m.group(1),
                "evidence": f"@keyframes {m.group(1)}",
            })

    if re.search(r'transition\s*:', html):
        features.append({
            "id": "css-transition",
            "type": "css_transition",
            "subtype": "transition",
            "evidence": "transition:",
        })

    # --- UI Elements (buttons, inputs, selects with IDs) ---
    ui_pattern = re.compile(
        r'<(button|input|select|textarea|canvas|video|audio)\b[^>]*\bid\s*=\s*["\']([^"\']+)["\']',
        re.IGNORECASE,
    )
    for m in ui_pattern.finditer(html):
        tag = m.group(1).lower()
        elem_id = m.group(2)
        features.append({
            "id": f"ui-{tag}-{elem_id}",
            "type": "ui_element",
            "subtype": tag,
            "evidence": elem_id,
        })

    # --- Named Functions (user-defined, non-trivial) ---
    func_pattern = re.compile(
        r'function\s+([a-zA-Z_]\w{2,})\s*\(', re.MULTILINE
    )
    seen_funcs = set()
    for m in func_pattern.finditer(html):
        fname = m.group(1)
        # Skip common boilerplate names
        if fname not in seen_funcs and fname not in (
            'undefined', 'arguments', 'constructor', 'toString',
        ):
            seen_funcs.add(fname)

    # Also catch const/let/var fn = (...) => and fn = function
    arrow_pattern = re.compile(
        r'(?:const|let|var)\s+([a-zA-Z_]\w{2,})\s*=\s*(?:\([^)]*\)|[a-zA-Z_]\w*)\s*=>',
    )
    for m in arrow_pattern.finditer(html):
        seen_funcs.add(m.group(1))

    assign_fn = re.compile(
        r'(?:const|let|var)\s+([a-zA-Z_]\w{2,})\s*=\s*function\s*\(',
    )
    for m in assign_fn.finditer(html):
        seen_funcs.add(m.group(1))

    for fname in sorted(seen_funcs):
        features.append({
            "id": f"function-{fname}",
            "type": "function",
            "subtype": "named",
            "evidence": fname,
        })

    # --- Tuned Constants ---
    # Look for ALL_CAPS = number patterns (game physics, config)
    const_pattern = re.compile(
        r'\b([A-Z][A-Z_]{2,})\s*=\s*(-?[\d.]+)\b'
    )
    for m in const_pattern.finditer(html):
        name = m.group(1)
        value = m.group(2)
        # Skip CSS hex colors and very generic names
        if name not in ('RGB', 'HSL', 'URL', 'NAN', 'MAX', 'MIN'):
            constants[name] = value

    # Also catch const UPPER_CASE = number
    const_decl = re.compile(
        r'(?:const|let|var)\s+([A-Z][A-Z_]{2,})\s*=\s*(-?[\d.]+)\b'
    )
    for m in const_decl.finditer(html):
        constants[m.group(1)] = m.group(2)

    # --- Meta Tags (rappterzoo:*) ---
    meta_pattern = re.compile(
        r'<meta\s+name\s*=\s*["\']rappterzoo:(\w[\w-]*)["\'][^>]*content\s*=\s*["\']([^"\']*)["\']',
        re.IGNORECASE,
    )
    for m in meta_pattern.finditer(html):
        features.append({
            "id": f"meta-rappterzoo-{m.group(1)}",
            "type": "meta_tag",
            "subtype": m.group(1),
            "evidence": m.group(2)[:60],
        })

    # Build summary
    type_counts = {}
    for f in features:
        t = f["type"]
        type_counts[t] = type_counts.get(t, 0) + 1

    return {
        "features": features,
        "constants": constants,
        "summary": type_counts,
    }


def verify_features(
    contract: dict,
    new_html: str,
    strict: bool = False,
) -> dict:
    """Verify that features from the original contract exist in new HTML.

    Args:
        contract: Feature contract from extract_features()
        new_html: The post-molt HTML to verify against
        strict: If True, constants must have exact same values.
                If False (default), constants just need to exist.

    Returns:
        dict with:
            passed: bool — True if verification passed
            total: int — total features checked
            preserved: int — features still present
            missing: list — features not found in new HTML
            missing_constants: list — constants not found
            preservation_ratio: float — 0.0 to 1.0
    """
    if not contract or not contract.get("features"):
        return {
            "passed": True,
            "total": 0,
            "preserved": 0,
            "missing": [],
            "missing_constants": [],
            "preservation_ratio": 1.0,
        }

    if not new_html:
        return {
            "passed": False,
            "total": len(contract["features"]),
            "preserved": 0,
            "missing": [f["id"] for f in contract["features"]],
            "missing_constants": list(contract.get("constants", {}).keys()),
            "preservation_ratio": 0.0,
        }

    missing = []
    preserved = 0
    new_lower = new_html.lower()

    for feature in contract["features"]:
        found = _check_feature_present(feature, new_html, new_lower)
        if found:
            preserved += 1
        else:
            missing.append({
                "id": feature["id"],
                "type": feature["type"],
                "evidence": feature.get("evidence", ""),
            })

    # Check constants
    missing_constants = []
    for name, value in contract.get("constants", {}).items():
        if strict:
            # Exact value must exist
            pattern = re.compile(r'\b' + re.escape(name) + r'\s*=\s*' + re.escape(value) + r'\b')
            if not pattern.search(new_html):
                missing_constants.append({"name": name, "expected": value})
        else:
            # Just the constant name must exist
            if name not in new_html:
                missing_constants.append({"name": name, "expected": value})

    total = len(contract["features"])
    ratio = preserved / total if total > 0 else 1.0

    # Pass if >=90% features preserved and no critical missing types
    critical_types = {"localstorage", "canvas", "audio"}
    critical_missing = [m for m in missing if m["type"] in critical_types]

    passed = ratio >= 0.9 and len(critical_missing) == 0

    return {
        "passed": passed,
        "total": total,
        "preserved": preserved,
        "missing": missing,
        "missing_constants": missing_constants,
        "preservation_ratio": ratio,
    }


def _check_feature_present(feature: dict, html: str, html_lower: str) -> bool:
    """Check if a single feature is present in the HTML."""
    ftype = feature["type"]
    evidence = feature.get("evidence", "")

    if ftype == "event_listener":
        # Check for addEventListener with same event type
        subtype = feature.get("subtype", "")
        return bool(re.search(
            r"""addEventListener\s*\(\s*['"]""" + re.escape(subtype) + r"""['"]""",
            html, re.IGNORECASE,
        ))

    elif ftype == "inline_handler":
        subtype = feature.get("subtype", "")
        return bool(re.search(
            r'\bon' + re.escape(subtype) + r'\s*=', html, re.IGNORECASE,
        ))

    elif ftype == "localstorage":
        # The key must still be referenced
        key = evidence
        return key in html

    elif ftype == "animation_loop":
        return evidence.lower() in html_lower

    elif ftype == "canvas":
        return evidence.lower().replace("'", "").replace('"', '') in html_lower.replace("'", "").replace('"', '')

    elif ftype == "audio":
        return evidence in html

    elif ftype == "keyboard_shortcut":
        return evidence in html

    elif ftype == "css_animation":
        name = feature.get("subtype", "")
        return bool(re.search(r'@keyframes\s+' + re.escape(name), html))

    elif ftype == "css_transition":
        return "transition:" in html_lower or "transition :" in html_lower

    elif ftype == "ui_element":
        elem_id = evidence
        return elem_id in html

    elif ftype == "function":
        fname = evidence
        # Check for function declaration or assignment
        return bool(re.search(r'\b' + re.escape(fname) + r'\b', html))

    elif ftype == "meta_tag":
        subtype = feature.get("subtype", "")
        return bool(re.search(
            r'rappterzoo:' + re.escape(subtype), html, re.IGNORECASE,
        ))

    # Unknown type — check evidence string directly
    if evidence:
        return evidence in html
    return True  # No evidence to check, assume present


def format_contract_for_prompt(contract: dict) -> str:
    """Format a feature contract as text to include in a molt prompt.

    This tells the LLM exactly what features must be preserved.
    """
    if not contract or not contract.get("features"):
        return ""

    lines = ["FEATURE CONTRACT — every item below MUST exist in your output:"]
    lines.append("")

    # Group by type
    by_type = {}
    for f in contract["features"]:
        t = f["type"]
        if t not in by_type:
            by_type[t] = []
        by_type[t].append(f)

    type_labels = {
        "event_listener": "Event Listeners",
        "inline_handler": "Inline Event Handlers",
        "localstorage": "localStorage Keys",
        "animation_loop": "Animation Loops",
        "canvas": "Canvas Rendering",
        "audio": "Audio System",
        "keyboard_shortcut": "Keyboard Shortcuts",
        "css_animation": "CSS Animations",
        "css_transition": "CSS Transitions",
        "ui_element": "UI Elements",
        "function": "Functions",
        "meta_tag": "Meta Tags",
    }

    for ftype, items in by_type.items():
        label = type_labels.get(ftype, ftype)
        lines.append(f"[{label}]")
        for item in items:
            lines.append(f"  - {item.get('evidence', item['id'])}")
        lines.append("")

    if contract.get("constants"):
        lines.append("[Tuned Constants — preserve these exact values]")
        for name, value in sorted(contract["constants"].items()):
            lines.append(f"  - {name} = {value}")
        lines.append("")

    return "\n".join(lines)
