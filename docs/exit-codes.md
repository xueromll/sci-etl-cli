# Exit codes

| Code | Meaning |
|------|---------|
| `0` | Success, including a search with no results. |
| `1` | A run aborted, a request failed, or a file couldn't be parsed. The message names the cause. |
| `2` | Invalid command-line usage. |
| `3` | Configuration problem: missing or invalid config, missing prompt, unset API key, or a failed `validate` check. |
| `4` | A required Python package is missing; the message says what to install. |
| `130` | A run was interrupted after saving state. |
