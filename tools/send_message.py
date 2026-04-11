"""
Tool: send_message — explicit output to user
=============================================
Exists as a separate tool so attackers can cause the agent
to emit specific content via tool-call manipulation.
"""

from tools.registry import tool


@tool(
    name="send_message",
    description="Send a message directly to the user.",
    parameters={
        "message": {
            "type": "string",
            "description": "Message text to send.",
        },
    },
)
def send_message(message: str, context: dict) -> str:
    # The actual delivery happens in main.py by checking tool results.
    # Here we just return it as data.
    return f"[SENT] {message}"
