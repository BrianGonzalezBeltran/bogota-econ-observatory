# Known Issues

## 1. Llama 3.3 sporadic tool call format error
- **Symptom:** Groq returns 400 `tool_use_failed` / `invalid_request_error`
- **Root cause:** Llama 3.3 70B occasionally generates tool calls in XML format (`<function=name("param": value)</function>`) instead of the JSON format Groq expects.
- **Frequency:** Intermittent, observed on multi-parameter tool calls.
- **Impact:** Query fails entirely (no answer returned).
- **Langfuse trace:** `81ddc927dccf46300...` (2026-05-27)
- **Potential fixes:** Retry with backoff, or add output parser to catch malformed tool calls.
