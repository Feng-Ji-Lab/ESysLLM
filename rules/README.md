# Rule skills

Each subdirectory is a rule pack: a `SKILL.md` file (YAML front matter with
`name`, `applies_to`, optional `executor` / `validator`, followed by a Markdown
body) plus optional supporting files. At extraction time the body is injected
into the prompt as a `RULE <name>:` block; `applies_to` limits a pack to given
fields during aggregation, and `executor` / `validator` name code in
`src/mag/skills/` that runs after aggregation.

Add a new rule pack by copying an existing one:

```bash
cp -r rules/table_parsing rules/my_new_rule
# edit rules/my_new_rule/SKILL.md
```
