"""Runtime compatibility patch for BLACK TECH cotizador.

Canonicalizes the redundant MarkBoss spelling "LCD INCELL" to "INCELL"
through the app's existing clean_quality() normalization path.
"""
import re as _re

_original_sub = _re.sub


def _sub(pattern, repl, string, count=0, flags=0):
    result = _original_sub(pattern, repl, string, count, flags)
    if pattern == r"\bC\s*/\s*M\b" and isinstance(result, str) and _re.search(r"\bINCELL\b", result):
        result = _original_sub(r"\bLCD\s+INCELL\b", "INCELL", result)
        result = _original_sub(r"\bINCELL\s+LCD\b", "INCELL", result)
    return result


_re.sub = _sub
