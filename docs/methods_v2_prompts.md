# How the v2 pipeline builds its prompts

Study 5 of the manuscript was run with the code in `src/mag` (the "mag" pipeline).
Its prompts are not the JSON documents shown for v1 in the manuscript's Supplemental
Material C; they are assembled at run time from three kinds of files. This note
describes what the model actually receives, so a reader can adapt the pipeline to a
new meta-analysis or compare it with v1.

## Files that define one meta-analysis ("schema bundle")

```
schemas/<ma>/fields.json    the target fields: name, type, items_type, allowed_values,
                            definition, scope (paper | sample), gender_specific, skills
schemas/<ma>/prompts.yaml   editable prose for every prompt slot (see below)
rules/<pack>/SKILL.md       a rule pack: YAML front matter (name, applies_to, executor,
                            validator) + a Markdown body that is injected as text
```

Only `name`, `type`, `items_type`, `allowed_values` and `definition` of each field are
sent to the model (as a JSON list under `FIELD DEFINITIONS:`). `scope` and
`gender_specific` steer aggregation; `skills` names the executors run after
aggregation. Other keys found in some bundles (`case_rules`, `value_labels`,
`skill_hints`) are documentation only — no code reads them.

## Stage 1 — one call per section, plus one per attached table or figure

`src/mag/extraction/prompt_builder.py::build_section_prompts`

System prompt (plain text, blocks joined by blank lines):

1. `stage1.system.role` — who the agent is and what to extract.
2. `stage1.system.sample_naming` — how to key values by sample ("Study 1 - college
   sample"), gender ordering `[total, female, male]`, how to treat subgroup series.
3. `stage1.system.effect_size_guidance` — where the effect size tends to be reported,
   sign conventions, averaging rules. This slot carries most of the per-meta-analysis
   coding rules (up to ~8 k characters for Ng 2023).
4. A fixed evidence policy (in code): every value must cite the verbatim `block_id` of
   the paragraph it came from and a short quote, or return the string `"None"`.
5. `FIELD DEFINITIONS:` + the JSON list from `fields.json`.
6. Every rule pack under `rules/`, each as `RULE <name>: <body>` — the batch driver
   loads all packs, not only the ones named for the current meta-analysis.

User prompt:

```
SECTION: <title> (<section_id>)
[<block_id>] paragraph text
[<block_id>] paragraph text
...
ATTACHED TABLE (block <id>): <caption + note>        # only on asset passes
Extract every target field from the text and any attached asset.
```

The response is constrained by a JSON schema generated from `fields.json`
(`src/mag/providers/_wire.py`); each field returns `extract_value`, `evidence_source`
(`block_id` + quote) and `warning`.

## Stage 2a — sample census (one call per paper)

`src/mag/extraction/aggregate_prompts.py::build_census_prompts` with
`stage2.census_system`: from all candidate sample descriptions, enumerate the distinct
recruited samples (study index, label, N, gender composition). Rules in the prose
cover gender splits, analysis-only partitions, grand totals and duplicates.

## Stage 2b — per-field aggregation (one call per field per paper)

`build_field_agg_prompts` (sample-scoped fields) or `build_flat_agg_prompts`
(paper-scoped fields): `stage2.field_system` / `stage2.flat_system`, the field's
definition, the value-shape instruction (`gender_shape` / `nongender_shape`), and the
rule packs whose `applies_to` names this field. The user prompt lists the fixed sample
keys from the census and every candidate from stage 1 with its section, study tag and
evidence. The model returns one value per sample key plus the candidate indices it
relied on and a short reasoning.

## Stage 3 — executors and validators (no model call)

`src/mag/derive/runner.py` runs the executors named in a field's `skills`
(e.g. `single_gender_fill`, `compute_weighted_mean_total`,
`estimate_yeart1_from_pubyear`, `infer_ethnicity_from_country`) and validators such as
`total_geq_sum`. Values set this way carry a `derivation` record in `paper_rich.json`
and are tagged `derived:<skill>` in `results/<ma>/scored_cells.csv`.

## What changed per meta-analysis in Study 5

The three user-prompt templates are identical across bundles. Every other slot —
role, sample naming, effect-size guidance, the three stage-2 system prompts and both
value-shape instructions — was rewritten for each of Vu, Ng, Bennett and Buecker, and
each bundle has its own `fields.json` and rule packs. The default bundle
(`schemas/default`) shows the neutral wording.

## Bowes 2023 is different

`scripts/extract_bowes.py` does not use stages 1–3. It makes one call per paper with
its own system prompt (in the script), the whole Marker text, text grids of every
numeric table and up to twelve table/figure images, and writes `extraction.json`
(study fields, samples, one row per effect size). `schemas/bowes2023/prompts.yaml`
exists but was not used for the reported results.

## v1 for comparison

`legacy/v1` (Studies 2–4) sends a JSON system prompt (`policies`, `definitions`,
`figure_policy`, `gender_difference_policy`, …), a JSON user prompt
(`context`, `extraction_request`) and a text block of table-reading rules; aggregation
uses `study_specific_prompt` / `flat_prompt` JSON templates. Those are the documents
reproduced in the manuscript's Supplemental Material C.
