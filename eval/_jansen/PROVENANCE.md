# Third-party reference data shipped for scoring

Everything in this directory was produced by other research teams and is
redistributed here only because the scoring scripts (`scripts/score_*.py`,
`eval/_dashboard/goldlib_*.py`) open these exact files. Nothing was edited; the
relative layout mirrors the source archives so paths in the scripts stay
recognisable. The full archives (several hundred MB, including primary-study
PDFs) are **not** redistributed — obtain them from the sources below.

| Path here | Source | Used for |
|---|---|---|
| `osfstorage-archive/coding_data.zip` | Jansen et al. (2025), OSF project for *Psychological Bulletin* 10.1037/bul0000501 — `coding_data.zip` (human_coding_final.xlsx, LLM_coding_clean_LL.xlsx, LLM_coding_raw.xlsx) | Jansen's eight-model codings re-scored on our scorer (Bennett, Buecker, Bowes descriptors, Ng, Vu) |
| `osfstorage-archive/Archive/analysis/d_long.xlsx` | same OSF project, revision-1 analysis file | Bennett gold; Ng `male_pct` / `dxgive` gold |
| `osfstorage-archive/Archive/Revision 2 files/d_long_final_v4.xlsx` | same OSF project, revision-2 analysis file | Jansen's per-effect-size codings for Bowes (`outcome_es`, `es_es`, `N_es`) |
| `Vu2023_15/All_data/WI_meta.csv` | Vu, Soraperra, Leib, van der Weele & Shalvi (2023), *Psychological Bulletin* 10.1037/bul0000398 — authors' OSF data | Vu gold (authors' own coding) |
| `Ng2023_34/Univariate/unimeta.csv` | Ng, Schleider, Horn & Weisz (2023), *Psychological Bulletin* 10.1037/bul0000395 — authors' OSF data | Ng `IPT` gold |
| `Ng2023_34/Study Measure ES Data/MeasureCharacteristics.xlsx` | same Ng OSF data | Ng `Source` / `MedCat` gold |

Gold for Bennett, Bowes and Buecker that we derived from the meta-analysts'
own supplementary data lives next to each scorer under `eval/<ma>/` (CSV).

Please cite the original authors when you use these files, and check each
source repository's licence before redistributing them further.
