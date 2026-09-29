"""Process exit codes of the ``holiday-card`` CLI (D16, #80).

The numbers are a public contract: scripts branch on them, so a value
never changes meaning. ``EXIT_CODES_HELP`` is the root ``--help`` epilog.
"""

from enum import IntEnum


class ExitCode(IntEnum):
    OK = 0
    ERROR = 1            # unexpected internal error (see --debug from P1-5)
    USAGE = 2            # bad flag/value, conflicting flags, not-found template/theme/file, invalid template
    CONSENT_REQUIRED = 3 # ai-asset first-use consent missing
    ENVIRONMENT = 4      # missing optional extra / API key, or output path not writable
    RAIL_REFUSED = 5     # ai-asset refused by hard category rails


_MEANINGS = {
    ExitCode.OK: "success",
    ExitCode.ERROR: "unexpected internal error (re-run with --debug for a traceback)",
    ExitCode.USAGE: "bad or conflicting flags, unknown template/theme/file, invalid template",
    ExitCode.CONSENT_REQUIRED: "ai-asset: first-use consent missing (--accept-ai-terms)",
    ExitCode.ENVIRONMENT: "missing optional extra or API key, or output path not writable",
    ExitCode.RAIL_REFUSED: "ai-asset: refused by the hard category rails",
}

EXIT_CODES_HELP = "Exit codes:\n\n" + "\n".join(
    f"  {code.value}  {_MEANINGS[code]}" for code in ExitCode
)
