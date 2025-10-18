import os
from string import Template


def _prompts_dir() -> str:
    here = os.path.dirname(os.path.abspath(__file__))
    return os.path.normpath(os.path.join(here, '..', 'prompts'))


def get_prompt_text(name: str) -> str | None:
    """Return the raw prompt text from backend/prompts/<name>, or None if missing."""
    path = os.path.join(_prompts_dir(), name)
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return f.read()
    except Exception:
        return None


def render_prompt(name: str, mapping: dict[str, str]) -> str | None:
    """Render a prompt template with ${VARS} using safe substitution.

    Returns the rendered string or None if the template file is missing.
    """
    raw = get_prompt_text(name)
    if raw is None:
        return None
    try:
        return Template(raw).safe_substitute(mapping or {})
    except Exception:
        # As a fallback, return the raw template if substitution fails
        return raw
