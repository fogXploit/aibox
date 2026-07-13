"""
Shared user-facing text for CLI commands.

Kept in a leaf module so both `slot` and `start` commands can import it
without creating import cycles.
"""

ANTIGRAVITY_AUTH_PANEL_TEXT = (
    "[bold yellow]Antigravity Authentication Recommendation[/bold yellow]\n\n"
    "Antigravity CLI (`agy`) authenticates with Google sign-in on a random local port.\n"
    "When you configure a Gemini slot, a short-lived container runs `agy`\n"
    "interactively on the host network so the browser callback works.\n\n"
    "Complete the Google sign-in in your browser, then exit the Antigravity CLI\n"
    "(type /quit or press Ctrl+C) to continue slot setup. The session is stored\n"
    "under this slot's `.gemini/` directory. No API keys are used or required."
)
