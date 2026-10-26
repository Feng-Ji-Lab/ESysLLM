---
name: ng_source_smallest_number
description: For the Source field in youth-depression psychotherapy trials, apply the codebook's "smallest number" rule when multiple raters complete one measure.
activates_on:
  - text_pass
  - asset_pass
applies_to:
  - Source
---

For every distinct measure in Methods §Measures, identify the rater /
informant who completes it. Source codes (lowest = highest priority):

  1 = Target youth (self-report)
  2 = Caregiver (parent / guardian; both parents are SEPARATE candidates
      with the same code 2)
  3 = Sibling
  4 = Peer
  5 = Teacher (or teacher-like adult: counselor, milieu worker, probation
      officer)
  6 = Therapist (treating clinician)
  7 = Researcher (RA, independent evaluator, clinician-rater;
      performance-based measures; interview-based judgments — K-SADS, CGI,
      GAF, C-GAS)
  8 = Life-event data (external records: arrests, attendance, grades,
      urinalysis from probation)
  9 = Unknown (not reported and authors didn't reply)

## Smallest-number rule (codebook p. 11)

When a measure has MULTIPLE sources (e.g., a factor score combining
multiple raters, or a measure given to both parent and child), code the
SMALLEST number. Examples:

  - "Family Assessment Device — composite of parent + youth self-report"
    → code 1 (smaller of 1 and 2)
  - "CBCL parent version + TRF teacher version pooled" → code 2 (smaller
    of 2 and 5)
  - "Interviewer-administered K-SADS with both parent and youth informants"
    → still code 7 (because the *rater* is the interviewer; the *informants*
    are 1 and 2 but the *source* is the researcher who codes it)

## Per-instrument informant lookup

Default informants for common Ng instruments:

  Youth self-report (1):
    BDI / BDI-II, CDI / CDI-S, CES-D / CES-DC, ATQ, DAS, CASQ, BHS, HSC,
    RSES, CSEI, PHCSCS, SPPC, MFQ, RADS-2, PHQ-9, Self-Report Coping
    Scale, SAS-SR, NRI, Loneliness Scale, IC

  Caregiver (2):
    CBCL parent version, CBQ parent version, FAD parent version, CRPBI,
    Conners-Wells parent (CPRS-R), FAM-III general parent,
    Parent-child Communication Scale parent version, Issues Checklist
    parent version

  Teacher (5):
    TRF (Teacher's Report Form), BASC-2 teacher version, MESSY teacher,
    CBCL Teacher Form

  Researcher / clinician-rated (7):
    K-SADS / KSADS-PL, CGI, GAF, C-GAS, CDRS-R, HRSD / Hamilton, all
    structured-interview measures where a trained interviewer codes
    severity, BMI / heart rate / urinalysis (performance-based)

  Unknown (9):
    Use only when the paper truly does not say (rare; older pre-2000 trials
    sometimes leave this implicit and authors are uncontactable)

## Emit-format

For each measure, emit ONE candidate per (measure × informant). A measure
given to both parent and youth → TWO candidates, one with Source=1 and one
with Source=2. The Stage 2 aggregator builds the union set per study.
