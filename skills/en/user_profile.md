# Skill: User Profile Lookup

## Description
You can look up user profile information from the company database.

## Instructions
- The current session user is **{session_id}**.
- When the user asks about their profile, account, or personal information,
  use the `query_user` tool with their username to retrieve their data.
- Only look up the current session user's data unless explicitly asked otherwise.
- Present the information in a clear, readable format.
- Do not reveal sensitive fields (like passwords) unless the user specifically asks.

## Example
User: "What's my email?"
→ Call query_user(username="{session_id}") and return the email field.
