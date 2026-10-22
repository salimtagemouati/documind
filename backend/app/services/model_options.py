"""Provider-specific generation options kept separate from prompts."""
import re


def sampling_options(model: str, temperature: float) -> dict:
    # Gemini 3+ is tuned for the provider default. Low temperature can cause
    # loops; newer releases deprecate the parameter entirely.
    match = re.search(r"(?:^|/)gemini-(\d+)", model)
    if match and int(match.group(1)) >= 3:
        return {}
    return {"temperature": temperature}
