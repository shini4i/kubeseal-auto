"""Custom styling for questionary prompts.

This module provides a consistent, visually appealing style for all
interactive CLI prompts.
"""

from questionary import Style

# Custom color palette using ANSI 256 colors for broad terminal compatibility
PROMPT_STYLE = Style(
    [
        ("qmark", "fg:#af87ff bold"),  # Purple question mark
        ("question", "bold"),  # Bold question text
        ("answer", "fg:#ff87d7 bold"),  # Pink submitted answer
        ("pointer", "fg:#ff87d7 bold"),  # Pink pointer for selections
        ("highlighted", "fg:#1c1c1c bg:#ff87d7 bold"),  # Dark text on pink background
        ("selected", "fg:#87d787"),  # Green for selected items
        ("separator", "fg:#6c6c6c"),  # Gray separator
        ("instruction", "fg:#6c6c6c italic"),  # Gray italic instructions
        ("text", ""),  # Default text
        ("disabled", "fg:#585858 italic"),  # Dark gray disabled items
        # Autocomplete completion menu styles (prompt_toolkit)
        ("completion-menu", "bg:#303030"),  # Dark background for menu
        ("completion-menu.completion", "fg:#ffffff bg:#303030"),  # White text on dark
        ("completion-menu.completion.current", "fg:#1c1c1c bg:#ff87d7 bold"),  # Dark on pink for selected
    ]
)

# Icon prefixes for prompts
POINTER = "❯ "
QMARK = "? "
