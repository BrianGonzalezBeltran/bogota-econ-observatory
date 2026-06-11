# Known Issues

## 1. Llama 3.3 sporadic tool call format error
- **Symptom:** Groq returns 400 `tool_use_failed` / `invalid_request_error`
- **Root cause:** Llama 3.3 70B occasionally generates tool calls in XML format (`<function=name("param": value)</function>`) instead of the JSON format Groq expects.
- **Frequency:** Intermittent, observed on multi-parameter tool calls.
- **Impact:** Query fails entirely (no answer returned).
- **Langfuse trace:** `81ddc927dccf46300...` (2026-05-27)
- **Potential fixes:** Retry with backoff, or add output parser to catch malformed tool calls.

## 2. Llama 3.3 invents non-existent tool parameters
- **Symptom:** Groq returns 400 `tool_use_failed` with schema validation error
- **Root cause:** Llama 3.3 70B occasionally generates parameters that don't exist in the tool schema (e.g., `include_codes` for `get_localities` which accepts no parameters).
- **Frequency:** Intermittent, observed on simple tool calls.
- **Impact:** Query fails entirely.
- **Example:** `get_localities(include_codes="True")` — parameter doesn't exist, and value is string instead of boolean.
- **Potential fixes:** Retry with backoff, or add a tool call validation/sanitization layer.
