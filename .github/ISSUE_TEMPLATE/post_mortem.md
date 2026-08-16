---
name: Production post-mortem
about: Document a real infrastructure incident or complex bug after it's resolved
title: "[post-mortem]: "
labels: post-mortem
---

**Summary**
One or two sentences: what broke, and for how long.

**Impact**
What was affected — which endpoint(s), how many requests/users, was it visible externally?

**Timeline**
- Detected:
- Root cause identified:
- Fix deployed:

**Root Cause**
What actually caused this — be specific (e.g. a config default, a race condition, a missing check).

**Resolution**
What fixed it. Link the PR/commit.

**Follow-ups**
Anything still open — a hardening task, a test to add, a doc to update.
