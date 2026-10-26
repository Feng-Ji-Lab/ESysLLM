# bas-bmi schema

Schema for meta-analyses studying the relationship between Body Appreciation
(BAS / BAS-2) and Body Mass Index (BMI).

14 fields extracted per paper. Study-specific fields use `"type": "object"`
with study names as keys. List values follow [total, female, male] order.

Select this schema with `MAG_SCHEMA_NAME=bas-bmi` in `.env`.
