# Default schema

Minimal schema adequate to smoke-test the MVP: Country, Sample, Mean age,
Correlation BAS-BMI, Number of studies.

Files:
- `fields.json` — the field list, types, gender/study nesting hints.
- `prompts.yaml` — editable Stage-1/Stage-2 prompt prose with `<<PLACEHOLDERS>>` (loaded by `mag.prompts.loader`).
- `code_book.json` — enum → human-readable mappings referenced via JSON pointer.

To define a project-specific schema, copy this folder (`cp -r schemas/default
schemas/my-project`), edit the files, and select it via `MAG_SCHEMA_NAME` or
through the UI once Phase 2 lands.
