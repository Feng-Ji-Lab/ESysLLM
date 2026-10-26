---
name: ng_mediator_lookup
description: For every measure in a youth-depression psychotherapy trial paper, look up its canonical MedCat (mediator category) using the instrument→category mapping below.
activates_on:
  - text_pass
  - asset_pass
applies_to:
  - MedCat
---

For every distinct measure mentioned in Methods §Measures (or in a Table 1 /
measure-list), determine its canonical MedCat code from the lookup below.
Emit ONE candidate per measure, with the MedCat code in `extract_value`
and the measure name + section/table location in `evidence_source`. The
aggregator will collapse to a set per study.

## Code → label → instrument lookup

### 1 — Negative cognition (codebook letter "a")
Cognitive distortions, dysfunctional attitudes, hopelessness, low self-esteem,
rumination, pessimistic attribution, dysfunctional thoughts.

  - ATQ (Automatic Thoughts Questionnaire)
  - CNCEQ (Children's Negative Cognitive Error Q)
  - DAS (Dysfunctional Attitude Scale)
  - BHS (Beck Hopelessness Scale)
  - HSC (Hopelessness Scale for Children)
  - CASQ / CASQ-R (Children's Attributional Style Q)
  - ACSQ (Adolescent Cognitive Style Q)
  - RSES (Rosenberg Self-Esteem Scale)
  - CSEI (Coopersmith Self-Esteem Inventory)
  - PHCSCS (Piers-Harris Children's Self-Concept Scale)
  - SPPC (Self-Perception Profile for Children)
  - Cognitive Triad Inventory for Children
  - Perceived Competence / Perceived Control Scale for Children
  - Personal Beliefs Inventory
  - Children's Nowicki-Strickland Internal-External Scale
  - Academic Self-Concept Scale
  - BASC-2 locus of control / self-esteem / sense of inadequacy
  - CPRS-R perfectionism
  - SPSI-R negative problem orientation

### 2 — Pleasant activities ("b")
Activity scheduling, hobbies, behavioral activation, relaxation
(NOT social — those go under 5).

  - PES (Pleasant Events Schedule)
  - PASCET behavioral activation
  - SAICA spare-time

### 3 — Problem solving ("c")
Primary control coping, active coping, generating solutions, conflict
resolution, asking for help.

  - Self-Report Coping Scale — problem solving
  - FAD — problem solving subscale
  - FICS — adolescent problem solving
  - List of Social Situation Problems
  - Children's Coping Strategies Checklist-R — active coping
  - ACS — problem solving / reference to others
  - SPSI-R rational problem solving
  - SOCQ — action stage
  - RSQ — primary control engagement coping

### 4 — Reframing ("d")
Secondary control coping, cognitive restructuring, distraction, acceptance,
finding the silver lining.

  - Frequency of Self-Reinforcement Attitudes Scale
  - Subjective Probability Questionnaire
  - Emotion Regulation Questionnaire — reappraisal
  - SPSI-R positive problem orientation
  - RSQ — secondary control engagement coping
  - PASCET cognitive skills

### 5 — Social engagement ("e")
Social skills, social support, prosocial behavior, loneliness, peer/dating
relationship quality.

  - MESSY (Matson Evaluation of Social Skills with Youngsters)
  - Children's Self-Efficacy for Peer Interaction
  - Number of friends / Satisfaction with friend relationships
  - BASC-2 interpersonal relations / social skills
  - SAS-SR friends / dating subscale
  - NRI peer / NRI friend social support
  - Loneliness Scale
  - Asperger Syndrome Diagnostic Interview / Autism Spectrum Quotient social
  - CBCL social withdrawal / social abilities
  - Social Adjustment Scale for Children and Adolescents
  - CPRS-R Social Problems subscale
  - SAICA peers / schooling
  - SAS-SR (modified) peer/social impairment

### 99 — Outcome (depression symptoms)
NOT a mediator — these are the dependent variable in the mediation paths.

  - BDI / BDI-II (Beck Depression Inventory)
  - CDI / CDI-S (Children's Depression Inventory)
  - CES-D / CES-DC
  - K-SADS depression severity / KSADS-PL depression
  - RADS-2 (Reynolds Adolescent Depression Scale)
  - MFQ (Mood and Feelings Questionnaire)
  - PHQ-9 / PHQ-A
  - CDRS-R (Children's Depression Rating Scale - Revised) — clinician-rated
  - HRSD / Hamilton Rating Scale for Depression
  - Bellevue Index of Depression

### l2 — Family functioning (L2)
Family dysfunction, expressed emotion, parent-youth conflict, cohesion,
communication problems.

  - FAD (Family Assessment Device) — any subscale except problem_solving
  - FAM-III general child / general parent
  - FICS (Family Interaction Coding System)
  - CRPBI (Children's Report of Parenting Behavior Inventory)
  - CBQ (Conflict Behavior Questionnaire)
  - IC (Issues Checklist)
  - Family Environment Scale — family cohesion
  - NRI parent / NRI parental social support
  - Child FACES Family Score
  - Conners-Wells Self-Report — family problems
  - BASC-2 — relations with parents
  - Parent-child Communication Scale
  - SAICA family life
  - FEICS (Family Emotional Involvement and Criticism Scale)
  - SAS-SR family

### l29 — Avoidance (L29)
Avoidant coping, wishful thinking, denial, precontemplation.

  - Self-Report Coping Scale — distancing
  - ACS — nonproductive coping
  - SPSI-R avoidant coping
  - SOCQ — precontemplation
  - RSQ — disengagement coping
  - PASCET — avoidance

## Tie-breaker rules

1. **Prioritize contents over title** (codebook p. 11). A "Problem Behavior
   Scale" with items about parent-youth conflict goes under l2, not 3.
2. **2/3 rule**: a measure with ≥2/3 items in one category codes as that
   category. If split evenly, code as the more specific of the two
   (e.g., l2 over 5 when family + general social are both touched).
3. **Multi-rater versions** (parent + child of the same FAD): each version
   is a SEPARATE candidate with the same MedCat but different Source.
4. **Combinations (codebook code 6)**: rare — if you encounter one, prefer
   the dominant single mediator over the combination code.
