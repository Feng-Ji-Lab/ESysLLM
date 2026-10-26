---
name: hien_arm_taxonomy
description: Map verbatim arm names from PTSD+AOD treatment trials to the 12 canonical category values (SN1 psychotherapy-controlled / SN2 placebo-controlled).
activates_on:
  - text_pass
  - asset_pass
applies_to:
  - category
---

For every randomized arm in the trial, assign the canonical category from
the 12-value vocabulary below. All lowercase, parentheses literal.

## Two sub-networks (do NOT mix)

**SN1 (psychotherapy-controlled)** — psychotherapy trials anchored on a
non-active psychotherapy control:
  - integrated
  - integrated trauma focused
  - trauma focused
  - psychotherapy (aod)
  - psychotherapy (control)
  - integrated and ptsd medication

**SN2 (placebo-controlled)** — pharmacotherapy trials anchored on pill
placebo:
  - medication (aod)
  - medication (both)
  - medication (ptsd)
  - placebo (control)
  - trauma focused and aod medication
  - trauma focused and placebo

A trial belongs to ONE sub-network. Pharmacotherapy-only trials — every arm
is either an active drug or a pill placebo — are entirely in SN2.

## Category definitions and canonical arm names

### integrated
Psychotherapy that simultaneously and explicitly targets BOTH PTSD and AOD
within the same protocol. NOT trauma-focused (no evidence-based trauma
processing).
  - "Seeking Safety", "SS"
  - "Integrated CBT for PTSD and SUD", "ICBT"
  - "Creating Change"

### integrated trauma focused
Integrated PTSD+AOD treatment that ALSO includes an evidence-based
trauma-processing component (PE, CPT, EMDR, NET).
  - "COPE" (Concurrent Treatment of PTSD and Substance Use Disorders using
    Prolonged Exposure)
  - "PE + SUD treatment integrated"
  - "Integrated Prolonged Exposure"
  - "Structured Writing Therapy + CBT for SUD"

### trauma focused
Standalone evidence-based trauma processing (PE, CPT, EMDR) WITHOUT AOD
integration.
  - "Prolonged Exposure" / "PE"
  - "Cognitive Processing Therapy" / "CPT"
  - "Culturally Adapted CPT"
  - "EMDR"
  - "Narrative Exposure Therapy" / "NET"

### trauma focused and aod medication
Trauma psychotherapy combined with an AOD pharmacotherapy in the SAME arm.
  - "PE + naltrexone"
  - "CPT + naltrexone"
  - "Prolonged Exposure + Naltrexone"

### trauma focused and placebo
Trauma psychotherapy combined with placebo pill (active-control for the
pharma arm of a 2×2 factorial).
  - "PE + placebo"
  - "Prolonged Exposure + placebo"

### psychotherapy (aod)
Active psychotherapy targeting AOD only, WITHOUT PTSD content.
  - "Relapse Prevention" / "RP"
  - "Relapse Prevention Training"
  - "Addiction counseling"
  - "Individual Drug Counseling"
  - "AUD treatment alone"
  - "SUD treatment alone"
  - "CBT for SUD alone"
  - "Alcohol-focused CBT"

### psychotherapy (control)
Non-active comparator psychotherapy condition.
  - "Treatment-as-Usual" / "TAU"
  - "Standard care"
  - "Community care"
  - "Waitlist" / "Wait-list control"
  - "Women's Health Education" / "WHE"
  - "Active monitoring"
  - "Attention control"
  - "Supportive counseling"

### medication (aod)
Pharmacotherapy targeting AOD only.
  - "Naltrexone"
  - "Disulfiram"
  - "Topiramate"
  - "Acamprosate"
  - "Naltrexone + disulfiram" (combined drug arm)

### medication (ptsd)
Pharmacotherapy targeting PTSD only.
  - "Sertraline"
  - "Paroxetine"
  - "Desipramine"

### medication (both)
Single pharmacotherapy with proposed action on BOTH PTSD and AOD.
  - "N-acetylcysteine" / "NAC"
  - "Prazosin"
  - "Doxazosin"

### integrated and ptsd medication
Integrated PTSD+AOD psychotherapy BUNDLED with a PTSD-targeting medication
in the SAME arm.
  - "Seeking Safety + sertraline"
  - "SS + sertraline"
  - "Integrated therapy + SSRI"

### placebo (control)
Pill placebo, no active pharmacotherapy. The standard active-control for
medication trials.
  - "Placebo"
  - "Placebo pill"
  - "Inert pill"

## Decision tree for ambiguous cases

  - "Integrated trauma focused" vs "integrated": does the protocol include
    EVIDENCE-BASED trauma processing (PE/CPT/EMDR/NET)? If yes → trauma
    focused; if no (present-focused like Seeking Safety) → integrated.
  - "Trauma focused" vs "integrated trauma focused": does the protocol
    explicitly address AOD too? Standalone PE → trauma focused; PE + SUD
    therapy in one protocol → integrated trauma focused.
  - "Psychotherapy (control)" vs "psychotherapy (aod)": is the therapy
    actively targeting AOD content? If yes (relapse prevention, drug
    counseling) → psychotherapy (aod); if no (TAU, waitlist, supportive
    counseling, community care, attention control) → psychotherapy (control).
  - For 2×2 factorial trials (a psychotherapy crossed with a pharmacotherapy
    so each participant gets one of 4 combinations), each of the 4 cells is
    a separate arm with its own compound category.

## Sanity checks before emitting a category

  - The category list MUST come from the 12-value vocabulary above. Do not
    invent new labels.
  - All arms in one trial must belong to the same sub-network (SN1 or SN2):
    if you've labeled one arm "psychotherapy (aod)" (SN1) and another
    "medication (aod)" (SN2) in the same trial without a compound bundle,
    re-examine — one of the labels is likely wrong, or the trial is
    actually 2×2 factorial and you missed a 4th arm.
  - Compound labels ("integrated and ptsd medication", "trauma focused and
    aod medication", "trauma focused and placebo") are reserved for arms
    that bundle TWO interventions in the SAME randomized condition.
  - If an arm receives both a psychotherapy AND a pharmacotherapy as part
    of one assigned condition, that's a single arm with a compound label —
    NOT two separate arms.
