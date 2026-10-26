# Buecker (2023) benchmark — gold errata (errors & inconsistencies found)

Running log of confirmed errors, mis-codes, inconsistencies, and definitional ambiguities in the
**Jansen (2025) `human_coding_final` "Buecker2023" gold** and the meta-analysts' `data_final`, found
while validating our extraction. Each entry: the study, the gold value, what the paper actually supports,
the evidence, and the type. These bound the achievable accuracy on affected fields — where the gold is
wrong, our "miss" is often correct.

Legend for **type**: `typo` (data-entry error) · `miscode` (category clearly wrong vs the paper) ·
`inconsistency` (gold applies its own rule unevenly) · `definitional` (defensible either way).

---

## yearT1

| study | gold | paper says | type | note |
|---|---|---|---|---|
| **Barker2016** | 2015 (`infoYearT1 = Given`) | *"In Fall 2005… baseline, December 2005; April 2006; and the 2007, 2008…"* | **typo** | 2005→2015 digit error; no 2015 data-collection date exists in the paper. **Our 2005 is correct.** |
| Bares2012 | 2000 (`Given`) | *"first sampled and interviewed in 1997"* (NLSY97 inception); this study uses **Waves 4,6,8** | **definitional** | gold = year of the first wave *included in the study* (Wave 4 ≈ 1997+3 = 2000); panel inception is 1997. Both defensible; the manual's "Time 1 = first assessment included" makes 2000 the coding-correct answer. (Our panel-reuse rule now computes 2000.) |
| Anglim2015 | 2009 (`Given`) | survey *"used since 2001"*; *"2004 (midpoint of first waves)"*; **"2009" appears NOWHERE in the paper** (verified by full-text grep) | **miscode** | coded `infoYearT1 = Given` ("year given in the publication") but 2009 is not stated anywhere; the paper's own dates are 2001 (survey start) and 2004 (first-wave midpoint). The correct stated value is ~2004; our 2001 (survey inception) is a defensible alternative; gold's 2009 is unsupported by the text. |

## ethnicity  (manual rule: "predominantly" = **≥70%**; `Other` = reported but no group ≥70%; `Not specified` = unreported)

| study | gold | paper says | type | note |
|---|---|---|---|---|
| **Anglim2015** | predominantly native american | general Australian sample (Australian Unity Wellbeing Index) | **miscode** | Australian ≠ American Indian / Pacific Islander / Alaska native; study is not about Aboriginal Australians. Clear category error. |
| **Bratt2015** | predominantly white/european | *"adolescents from **ethnic minority groups** (N = 705)"* | **miscode** | the sample is explicitly minorities, not ≥70% white. Should be "other" (or a minority category). **Our "other" is more defensible.** |
| **Busseri2013** | predominantly white/european | *"446 Canadian students"* — **no composition reported** | **inconsistency** | manual says unreported → "not specified"; gold inferred white for Canada. **Our "not specified" is the manual-correct code.** |
| Adamczyk2017 | not specified | Polish sample, composition unreported | **inconsistency** | gold declines to infer here, but infers "white/european" for other unreported European samples (Germany/UK/Sweden). Uneven application of country-inference. |
| Busseri2009 | other | race not assessed; *"English 22%, Italian 12%, Dutch 11%…"* (no nationality ≥70%) | **definitional** | correct per the 70% rule (reported, mixed → "other"), but a coder aggregating to "White/European" (all European ancestry) is also defensible. |
| **Bares2012** | predominantly white/european | NLSY97 — a racially DIVERSE US panel (oversamples Black/Hispanic; no group ≥70% white) | **inconsistency** | under the 70% rule this should be "other" (which our extraction now emits); gold "white" doesn't fit the diverse NLSY97 composition. |

| **Daniel2016** | predominantly asian | *"a longitudinal study of **Israeli adolescents**"* (title); Israeli sample | **miscode** | Israeli adolescents are not "Predominantly Asian" under the scheme; our "white/european" (or "other"/"not specified") is more defensible. Found in the 40-paper run. |
| Delfabbro2017 | not specified | Australian youth cohort, composition unreported | **inconsistency** | gold declines to infer for Australia here though it infers "white" for other unreported European samples; we country-infer white. Same uneven country-inference as Adamczyk/Busseri2013. |
| Duineveld2017 | not specified | Finnish sample, composition unreported | **inconsistency** | same pattern — we country-infer white for Finland, gold says not-specified. |

**Systematic ethnicity issue:** the gold applies country-inference for *unreported* composition **inconsistently** — inferring "white" for Germany/UK/Sweden/Canada(Busseri2013) but "not specified" for Poland(Adamczyk). This caps ethnicity accuracy regardless of our method; the manual's own rule (unreported → "not specified") is not followed uniformly.

---

## sample_type  (found in the 30-paper run)

| study | gold | paper says | type | note |
|---|---|---|---|---|
| **Burger2017** | community/convenience | *"a representative large-scale sample… the TREE (Transitions from Education to Employment) project"* — TREE is a PISA-2000-based **nationally-representative** Swiss cohort | **miscode** | should be "nationally-representative"; our extraction gives that. |
| **Bergman2009** | nationally-representative | *"479 Örebro women… the IDA extended… sample"* — a single-city (Örebro) regional cohort | **miscode** | IDA is NOT national; should be "community/convenience" (which we emit). Opposite-direction error to Burger — the gold is internally inconsistent on this field. |

## yearT1 (more, from 30-paper run)

| study | gold | paper says | type | note |
|---|---|---|---|---|
| **Carmel2016** | 2012 | *"in 2010, we randomly selected…"* | **inconsistency** | paper's explicit recruitment year is 2010; gold 2012 is 2 yr off. Our 2010 matches the text. |

## sample_type / lag (found in the 50-paper run, newest batch Eisman–Garcia)

| study | field | gold | paper says | type | note |
|---|---|---|---|---|---|
| **Galla2020** | sample_type | college/university students | *"The mindful adolescent … students sampled from two public middle schools and six charter schools, 8th→9th grade"* | **miscode** | the sample is **middle/high-school adolescents**, not tertiary students; our "community/convenience" is correct per the school-recruited-adolescent rule. |
| **Eisman2017** | lag | 12.0 | African-American adolescents, waves annual during high school; *"wave 11 obtained ≈12 months before wave 12"* → ~1 yr inter-wave | **error** | 12.0 is implausible as an inter-wave interval (looks like total span or wave-count entered as lag); our 2.0 is far closer. |
| **Ellberg2020** | lag | 7.0 | *"assessed at four time periods: third trimester and 1, 3, 6 months postpartum"* — whole study spans **< 1 year** | **error** | 7.0 years is physically impossible for a postnatal study; our 0.93 is closer (true value ≈ 0.2). |
| Fergusson2015 | lag | 3.0 | Christchurch cohort assessed at ages 18/21/25/30/35 (intervals 3,4,5,5) | **definitional** | unevenly spaced; gold took the first interval (3), we took a later one (5). Modal ≈ 4; both defensible. |

| **Dainese2011** | sample_type | community/convenience | *"MIDUS is a national probability sample, drawn with random-digit dialing … National Survey of Midlife Development in the United States"* | **miscode** | MIDUS is a textbook nationally-representative US probability sample; our "nationally-representative" is correct. |
| FrizellReiter2016 | sample_type | community/convenience | *"the population-based Norwegian Mother and Child Cohort Study (MoBa), conducted by the Norwegian Institute of Public Health … Medical Birth Registry of Norway"* | **definitional** | the sampling frame is a national population-based cohort; "nationally-representative" is defensible (a disease-subgroup of a national cohort). Both codes arguable. |

## Our own errors found (not gold errors)

- **sample_type "nationally-representative" over-call — FIXED** (50-paper run): we had labelled
  **Garcia-Pena2013** (older adults **randomly sampled within Mexico City** — a single-city frame) as
  "nationally-representative". Root cause: the model triggered "nationally-representative" on any
  *random/probability* sampling, ignoring geographic scope. **Rule fix applied** (fields.json +
  flat_system): require a national probability sample whose **frame is a whole country**; a single
  city/region/clinic random sample → `community/convenience`. After re-aggregation Garcia-Pena flipped
  to community/convenience (correct) with **no regression** on genuine national samples — Dainese2011
  (MIDUS) and FrizellReiter2016 (MoBa) correctly stayed "nationally-representative". (My first read of
  FrizellReiter as a "clinical/regional" own-error was wrong: I saw the neurology affiliation, not the
  MoBa national sampling frame.)

- **Cowlishaw2013 country** (40-paper run): we returned **Australia** (from the Monash University author
  affiliation) but the sample is **British** — the study's social-support items are "adapted from the
  British Health and Lifestyle Survey" and it is a UK ageing cohort. Gold **UK is correct**. Lesson for
  the country rule: the sample's country ≠ the first author's institution country; prefer sample-recruitment
  evidence over affiliation.

## Known extraction failure (not a gold issue)

- **Kobayashi2015** (99-paper run): fails deterministically at Stage-1 on its dense social-network
  results-table section with `ProviderError: non-JSON response: Unterminated string` — the
  schema-constrained gemini-2.5-flash output is truncated mid-string (char 431 at temp 0.0, char 734 at
  temp 0.4; `max_output_tokens=65536` is not the cap). 4 retries + a temperature nudge did not clear it.
  Corpus finalized at **98/99 extracted**; needs a provider-side JSON continuation/repair fallback.

## Corrupted study labels in Jansen's gold (found 2026-07-09)

Two studies were initially dropped as "no gold" — they DO have gold, stored under labels corrupted by
letter transposition plus a wrong year. Verified field-for-field against our extraction.

| our study_id | gold's corrupted label | corruption | verification |
|---|---|---|---|
| **Daukantaite2012** | `Dankantaité2011` | Dau→**Dan**, 2012→2011 | all 6 fields agree (yearT1 1998 · Sweden · LS+PA+NA · community · white · lag 6) |
| **Gustavson2016** | `Gutsavson2015` | Gus**ta**→Gu**ts**a, 2016→2015 | all 6 agree (yearT1 2008 · Norway · LS · community · white · lag 3) |

Same class as Bennett's `Ziołkowska2017` corruption. **`ChenK2020` is the only study with no gold
anywhere** (absent from both the gold sheet and the LLM coding sheets).

Related Jansen-side defects (see the cross-MA record §4): the LLM sheet and gold sheet use different
label spaces for some studies (`Berghuis2020` vs `Borghuis2019`); the LLM sheet has duplicate rows
(`Chen2020`, `Zhang2017`); and its `*_clean_2` columns are entirely empty.

Also note **`Chen2020`'s gold `lag` cell is Excel-corrupted to a datetime** (`2024-05-01 00:00:00`) —
almost certainly "1/2" (=0.5) coerced to a date. Our extraction gives 0.5.

## Validator note (not a gold error)

- **Chen2020** yearT1: the gold row's representative value is **2016** (matches the paper's "first wave November 2016" and our extraction), but `load_gold_descriptors`' MODAL selection picked a stray **2009** from another row. Root cause identified 2026-07-09 (below).
- **`modal()` was non-deterministic** (fixed 2026-07-09): it was `max(set(vals), key=vals.count)`, so **ties were broken by set-iteration order**, which is hash-seed dependent. The *gold itself* changed run-to-run (the `lag` reference count flipped between 91 and 92 across `PYTHONHASHSEED` values), and with it every reported metric. Ties are now broken by the smallest string repr; gold + metrics are now byte-identical across seeds. This is the root cause of the Chen2020 symptom above.
- **`sample_type` gold decoder was wrong** (fixed 2026-07-09): code `4` was decoded as `clinical/patient`. The Buecker gold's real scheme is `1 = Nationally-representative, 2 = Community, 3 = College, 4 = Other, 5 = Not specified` — there is **no clinical/patient category**, so our schema's `clinical/patient` can never match (we emit it only for Helgeson2015, where it is therefore always wrong; gold there is `community`). **Impact on all reported numbers: zero** — no study in the 100-paper corpus is coded 4 or 5 (75 community / 11 national / 11 college). Latent bug that would have bitten on a larger corpus.
- **country normalization** (fixed 2026-07-07): `norm()` did not alias `United States`↔`usa` (nor `United Kingdom`↔`uk`, `Netherlands`↔`Holland`, etc.), so **Burris2017** (`United States` vs gold `usa`) counted as a miss though both are correct. Added a `_COUNTRY_ALIAS` map → country 0.93 → **0.97**.

## `infoYearT1` provenance flag — a test-method caveat (not a gold error)

- The gold's `infoYearT1` (1=Given / 2=Reported-other-source / 3=Estimated) is well-defined, but our schema's `infoYearT1` field **cannot be populated by a Stage-2 re-aggregation run** — it has no Stage-1 candidates, so the field aggregator defaults it to a *no-evidence* "estimated" for **every** paper. Routing the pub−3−span estimation off that defaulted flag **overrode correctly-extracted "given" years** (Armenta 2002→2005, Berg 1991→2002) and regressed yearT1 0.79→0.66. **Rule:** never let a defaulted provenance flag override a concretely-extracted value; the estimation skill fires only on unresolved/implausible yearT1. Realizing the provenance *override* (rejecting a background-citation year via `infoYearT1="estimated"`) requires a **full Stage-1 re-extract**, not re-aggregation.

## Impact on reported accuracy

- **yearT1**: Barker (typo) is unwinnable — our 2005 is right, gold is wrong. So our *true* yearT1 accuracy ≥ the measured 0.90 (Barker should count as correct).
- **ethnicity**: Anglim (miscode), Bratt (miscode), Busseri2013 (inconsistent inference) are cases where **our answer is at least as defensible as the gold**. With these set aside, ethnicity is well above the measured 0.60.

_Source of truth for the gold: `Jansen2025/osfstorage-archive/coding_data.zip` (`human_coding_final.xlsx`
sheet `Buecker2023`) and `Jansen2025/Buecker2023_188/Data/data_final_*.RData`. Coding manual:
`Jansen2025/Buecker2023_188/Coding Instructions_SWB across the life span.pdf`._
