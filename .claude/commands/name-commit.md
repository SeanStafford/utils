---
description: Suggest a conventional commit message for staged changes
allowed-tools: Bash(git diff:*), Bash(git log:*), Bash(git commit:*)
---

Review the currently staged git changes and suggest a conventional commit message.

**Instructions:**
1. Run `git diff --staged` to see what's staged
2. Run `git log -3 --oneline` to see recent commit style
3. Analyze the changes and suggest a conventional commit message following this format:
   - `feat:` for new features
   - `fix:` for bug fixes
   - `docs:` for documentation changes
   - `test:` for adding/modifying tests
   - `refactor:` for code changes without new features or fixes
   - `style:` for code formatting, linting fixes, and whitespace changes (no functional changes)
   - `perf:` for performance improvements
   - `chore:` for build process, dependencies, tooling

**Style Guidelines:**
   - Use past tense for the verb following the prefix (e.g., "added", "fixed", "updated")
   - There should be a mention of a purpose like "added performance metrics to enhance model capabilities" instead of just "added performance metrics"
   - When a function is mentioned in a message, the trailing parenthesis should not be included, e.g. print() should be print
   - For `fix:` commits, it is more important to describe what was done to fix the issue than to describe the bug itself
   - If the changes are very limited (few to no lines of actual code changed and any changes have minimal consequences), then keep the description concise and action-oriented (10 - 20 words)
      - However, you can include something extra notes jotted down at the end if there was something cool added in this commit (this is on top of the word limit)
   - Else for more substantial changes, have the 10 - 20 word topline, but also include bullet point, one for each significant change

4. Present the suggested commit message to me clearly
5. Ask to execute the commit and wait for explicit user confirmation.
6. If confirmed, execute: `git commit -m "the message"`

Never add extra text to the commit message.
