# Reproduction and validation

Checked 2026-10-27. Code and verification are AI-assisted.

Local result: **34 tests passed**.

Setup: python -m pip install -e .

Run:

```text
python -m unittest discover -s tests -v
python -m budget_variance_forecast.demo
python -m budget_variance_forecast.baseline
```

All listed demo entrypoints completed. Source fingerprints use UTF-8 source bytes with CRLF normalized to LF; pinned external data retain their own raw-byte hashes.

[Machine-readable evidence](validation-latest.json). Historical validation files describe earlier snapshots; old commit IDs may have changed after privacy-related history rewriting.

Tests do not establish production readiness, actual business gains or independent personal mastery.
