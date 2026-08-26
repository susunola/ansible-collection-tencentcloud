# Contributing

Keep SDK calls in small testable functions and do not log credentials. New
state-changing modules must be idempotent and support check mode where possible.

```bash
ansible-test sanity --docker default
ansible-test units --docker default
ansible-galaxy collection build
```
