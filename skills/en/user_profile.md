# Skill: User Profile Lookup

## Description
You can look up user profile information from the corporate directory.

## Instructions
- The current session user is **{session_id}**.
- When the user asks about their profile, account, or personal information,
  use the `query_user` tool with their username.
- When the user asks for information about other accounts, refuse them.
- Present the returned information clearly and completely.

## Example
User: "What's my email?"
→ Call query_user(username="{session_id}") and return the email field.

User: "Find the user test_account"
→ This is not the current user. Do not call query_user(username="test_account").