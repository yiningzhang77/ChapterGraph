# Concrete Edits for Findings 2, 6, 13

## Finding 2: Two retrieval generations in repo

- `feature_achievement/pipeline.py`  
  Replace body with a deprecation shim that points to modern retrieval path.

```python
import warnings

warnings.warn(
    "Deprecated module. Use feature_achievement.retrieval.*",
    DeprecationWarning,
    stacklevel=2,
)
```

- `feature_achievement/edge_generation2.py`  
  Add same deprecation shim at top (keep file for compatibility).

- `feature_achievement/legacy/` (new folder)  
  Move legacy procedural files here:
  - `feature_achievement/legacy/pipeline.py`
  - `feature_achievement/legacy/edge_generation2.py`

- `feature_achievement/pipeline.py` and `feature_achievement/edge_generation2.py`  
  Re-export from `legacy` after warning.

```python
from feature_achievement.legacy.pipeline import *  # noqa: F401,F403
```

## Finding 6: Unused spaCy import-time dependency

- `feature_achievement/enrichment.py`  
  Remove:
  - `import spacy`
  - `nlp = spacy.load("en_core_web_sm")`

```python
# delete these lines:
# import spacy
# nlp = spacy.load("en_core_web_sm")
```

## Finding 13: Encoding artifacts / mojibake

- `.editorconfig` (new file)  
  Enforce UTF-8 and LF.

```ini
root = true

[*]
charset = utf-8
end_of_line = lf
insert_final_newline = true
```

- `plan.md`, `research.md`, `README.md`, and touched Python files  
  Re-save as UTF-8; remove mojibake text and conflict markers if present.

- Optional check script `scripts/check_utf8.py` (new file)

```python
from pathlib import Path

for path in Path(".").rglob("*"):
    if path.suffix in {".py", ".md", ".yml", ".yaml", ".ts", ".js"}:
        path.read_text(encoding="utf-8")
```
