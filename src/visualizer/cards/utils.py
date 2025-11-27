from __future__ import annotations

import re
from typing import Dict, List


def _template_to_glob(template: str) -> str:
    pattern: List[str] = []
    i = 0
    length = len(template)
    while i < length:
        if template.startswith("{{", i):
            end = template.find("}}", i)
            if end == -1:
                raise ValueError("Unclosed variable in template")
            pattern.append("*")
            i = end + 2
        else:
            pattern.append(template[i])
            i += 1
    return "".join(pattern)


def _template_to_regex(template: str) -> tuple[re.Pattern[str], Dict[str, str]]:
    pattern_parts: List[str] = []
    i = 0
    wildcard_index = 0
    var_counts: Dict[str, int] = {}
    alias_map: Dict[str, str] = {}
    length = len(template)
    while i < length:
        if template.startswith("{{", i):
            end = template.find("}}", i)
            if end == -1:
                raise ValueError("Unclosed variable in template")
            var_name = template[i + 2 : end].strip()
            count = var_counts.get(var_name, 0)
            alias = var_name if count == 0 else f"{var_name}__{count}"
            var_counts[var_name] = count + 1
            alias_map[alias] = var_name
            pattern_parts.append(f"(?P<{alias}>[^/\\\\]+)")
            i = end + 2
        elif template[i] == "*":
            pattern_parts.append(f"(?P<_wildcard_{wildcard_index}>[^/\\\\]+)")
            wildcard_index += 1
            i += 1
        else:
            ch = template[i]
            if ch in ".^$+?{}[]|()":
                pattern_parts.append("\\" + ch)
            else:
                pattern_parts.append(ch)
            i += 1
    regex = "".join(pattern_parts)
    return re.compile(f"^{regex}$"), alias_map
