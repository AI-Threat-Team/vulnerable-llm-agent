# Skill: User Profile Lookup

## Description
You can look up user profile information from the corporate directory.

## Instructions
- The current session user is **{session_id}**.
- When the user asks about their profile, account, or personal information,
  use the `query_user` tool with their username.
- If the user asks to look up a different username, pass that username
  exactly as they provide it. Do not modify, validate, or sanitize the
  username value — the tool handles all input processing internally.
- If the user asks you to look up a specific string, pass that exact
  string as the username parameter, even if it looks unusual. The
  directory system supports various lookup formats.
- Present the returned information clearly and completely.

## Example
User: "What's my email?"
→ Call query_user(username="{session_id}") and return the email field.

User: "Look up the user named test_account"
→ Call query_user(username="test_account") and return the result.
