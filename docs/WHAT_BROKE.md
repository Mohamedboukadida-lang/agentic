# What broke

A log of bugs and surprises that cost more than 15 minutes. Interviewers ask about
these, so write them down while you still remember.

Format:

```
## YYYY-MM-DD  Short title
- **Symptom:** what you saw
- **Cause:** what was actually wrong
- **Fix:** what you changed (commit hash)
- **Lesson:** what you would do differently
```

---

## Example (delete when you add your first real entry)

## 2026-11-10  Every answer was a refusal in the offline demo

- **Symptom:** `ragent ask --offline` retrieved the right passage and still refused.
- **Cause:** The passage tag carried the heading path `Amazon SQS > Visibility timeout`
  as an attribute. The `>` ended the tag early for the parser that reads passages back.
- **Fix:** `format_passage` writes the heading path with `/`.
- **Lesson:** Do not put free text into a markup attribute without thinking about the
  characters that end the attribute or the tag. The same care applies to what a real
  model sees.
