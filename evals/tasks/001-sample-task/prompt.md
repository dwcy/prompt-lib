Create a new module `setup/src/cabal/text_utils.py` containing a single function:

```python
def slugify(text: str) -> str
```

Behaviour: lowercase the input, replace every run of non-alphanumeric characters with a single hyphen, and strip leading/trailing hyphens. An input with no alphanumeric characters returns an empty string.

Also write pytest tests in `setup/tests/test_text_utils.py` covering: a plain sentence, repeated separators, leading/trailing punctuation, an already-clean slug, the empty string, and a punctuation-only string.

Do not modify any other files.
