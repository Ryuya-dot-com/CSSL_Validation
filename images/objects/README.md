# Object Images

This directory contains abstract object SVGs used by the browser task.

Design policy:

- Use novel abstract forms rather than real objects to avoid prior labels.
- Separate objects by outline family, color palette, rotation, and internal marks.
- Avoid placing the same visual family in a single 3-object learning trial.
- Prefer the generated SVG files for reproducibility; do not replace them with
  semantically nameable pictures unless the task design is changed.

Regenerate:

```bash
python3 stimulus_tools/generate_object_svgs.py
```
