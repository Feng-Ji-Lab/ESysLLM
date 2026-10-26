"""Verify each Marker JSON's first-page text matches the expected paper title.

Surface mismatches like Foa2013 (PMC3846982 turned out to be a Med-Toxicology
commentary, not the actual JAMA trial).
"""
from __future__ import annotations

import difflib
import json
import re
from pathlib import Path

ROOT = Path("/projects/code/meta_analysis_agent")
PROCESSED = ROOT / "data" / "processed"

# (key, expected first-author surname(s), year, ~title keywords)
EXPECTED = {
    "hien2024": [
        ("Back2016",      "back",       2016, "n-acetylcysteine veterans ptsd substance"),
        ("Back2019",      "back",       2019, "concurrent treatment substance use ptsd prolonged exposure"),
        ("Batki2014",     "batki",      2014, "topiramate alcohol use disorder veterans ptsd"),
        ("Brady2005",     "brady",      2005, "sertraline alcohol dependence posttraumatic"),
        ("Capone2018",    "capone",     2018, "integrated cbt ptsd substance iraq afghanistan"),
        ("Foa2013",       "foa",        2013, "concurrent naltrexone prolonged exposure alcohol dependence ptsd"),
        ("Hien2004",      "hien",       2004, "promising treatments women comorbid ptsd"),
        ("Hien2009",      "hien",       2009, "multisite behavioral interventions women ptsd"),
        ("Hien2015",      "hien",       2015, "seeking safety sertraline ptsd alcohol"),
        ("McGovern2015",  "mcgovern",   2015, "treatments co-occurring substance use ptsd"),
        ("Mills2012",     "mills",      2012, "integrated exposure-based ptsd substance"),
        ("Myers2015",     "myers",      2015, "intimate partner violence ptsd alcohol"),
        ("Najavits2018",  "najavits",   2018, "creating change seeking safety veterans"),
        ("Norman2019",    "norman",     2019, "integrated exposure coping skills ptsd alcohol"),
        ("Pearson2019",   "pearson",    2019, "culturally adapted cognitive processing native american"),
        ("Petrakis2006",  "petrakis",   2006, "naltrexone disulfiram alcohol ptsd"),
        ("Petrakis2012",  "petrakis",   2012, "noradrenergic serotonergic naltrexone ptsd alcohol"),
        ("Petrakis2016",  "petrakis",   2016, "prazosin veterans ptsd alcohol dependence"),
        ("Ruglass2017",   "ruglass",    2017, "concurrent prolonged exposure ptsd substance"),
        ("Sannibale2013", "sannibale",  2013, "cognitive behaviour ptsd alcohol"),
        ("Schafer2019",   "schäfer|schafer", 2019, "seeking safety relapse prevention ptsd"),
        ("Simpson2015",   "simpson",    2015, "prazosin alpha-1 alcohol dependence ptsd"),
        ("vanDam2013",    "dam",        2013, "trauma-focused ptsd cbt substance"),
        ("Zlotnick2009",  "zlotnick",   2009, "cognitive-behavioral incarcerated women ptsd"),
    ],
    "ng2023": [
        ("Ackerson1998",  "ackerson",   1998, "cognitive bibliotherapy adolescent depressive"),
        ("Asarnow2002",   "asarnow",    2002, "cognitive-behavioral family education depression"),
        ("Asarnow2005",   "asarnow",    2005, "effectiveness quality improvement adolescent depression"),
        ("Brent1997",     "brent",      1997, "clinical psychotherapy adolescent depression cognitive family"),
        ("DeCuyper2004",  "cuyper",     2004, "treating depressive symptoms schoolchildren"),
        ("Dietz2015",     "dietz",      2015, "family-based interpersonal psychotherapy preadolescents"),
        ("Fleming2012",   "fleming",    2012, "sparx computerized cbt adolescents excluded"),
        ("Garber2009",    "garber",     2009, "prevention depression at-risk adolescents"),
        ("Gillham2012",   "gillham",    2012, "group cognitive-behavioral depression prevention"),
        ("Lewinsohn1990", "lewinsohn",  1990, "cognitive-behavioral depressed adolescents"),
        ("Liddle1990",    "liddle",     1990, "cognitive-behaviour depressed primary school"),
        ("McCarty2013",   "mccarty",    2013, "positive thoughts action depression early adolescents"),
        ("Merry2012",     "merry",      2012, "sparx computerised self help adolescents"),
        ("Mufson2004",    "mufson",     2004, "interpersonal psychotherapy depressed adolescents"),
        ("Reed1994",      "reed",       1994, "social skills training depression adolescents"),
        ("Reynolds1986",  "reynolds",   1986, "cognitive-behavioral relaxation training depression"),
        ("Rohde2004",     "rohde",      2004, "cognitive-behavioral adolescents comorbid major depression conduct"),
        ("Rohde2014",     "rohde",      2014, "indicated cognitive behavioral depression bibliotherapy"),
        ("Rossello1999",  "rossello",   1999, "cognitive-behavioral interpersonal puerto rican adolescents"),
        ("Santomauro2016","santomauro", 2016, "depression adolescents autism pilot"),
        ("Stark1987",     "stark",      1987, "self-control behavioral problem-solving depression children"),
        ("Stasiak2014",   "stasiak",    2014, "pilot computer-based cognitive behavioural adolescents depression"),
        ("Stice2008",     "stice",      2008, "brief cognitive-behavioral depression prevention high-risk"),
        ("Szigethy2007",  "szigethy",   2007, "cognitive-behavioral adolescents inflammatory bowel"),
        ("TADS2004",      "march|tads", 2004, "fluoxetine cognitive-behavioral combination adolescents depression"),
        ("Tang2009",      "tang",       2009, "school-based intensive interpersonal psychotherapy adolescents suicidal"),
        ("Vostanis1996",  "vostanis",   1996, "treatment children adolescents depression lessons"),
        ("Weisz2009",     "weisz",      2009, "cognitive-behavioral usual care youth depression"),
        ("Young2006",     "young",      2006, "interpersonal psychotherapy adolescent skills training"),
        ("Young2010",     "young",      2010, "preventing depression interpersonal adolescent"),
        ("Yu2002",        "yu",         2002, "preventing depressive symptoms chinese children"),
    ],
    "vu2024": [
        ("Bartling2014",     "bartling",          2014, "willful ignorance deflect punishment"),
        ("Cerrone2019",      "cerrone",           2019, "deciding on behalf others selfishness"),
        ("Conrads2013",      "conrads",           2013, "strategic ignorance ultimatum bargaining"),
        ("Dana2007",         "dana",              2007, "moral wiggle room illusory preference"),
        ("Exley2015",        "exley",             2015, "excusing selfishness charitable giving risk"),
        ("Exley2021",        "exley|kessler",     2020, "information avoidance image concerns"),
        ("Grossman2014",     "grossman",          2014, "strategic ignorance robustness social preferences"),
        ("Grossman2017",     "grossman|weele",    2017, "self-image willful ignorance social"),
        ("Jarke-Neuert2022", "jarke|lohse",       2020, "strategic ignorance time pressure"),
        ("Kappes2018",       "kappes",            2018, "uncertainty social decisions prosocial"),
        ("Larson2009",       "larson|capra",      2009, "moral wiggle room comment"),
        ("Lind2019",         "lind|nyborg",       2019, "save planet close eyes strategic"),
        ("Matthey2011",      "matthey|regner",    2011, "cognitive dissonance other-regarding"),
        ("Moradi2018",       "moradi|nesterov",   2018, "moral wiggle room reverted information avoidance"),
        ("Stuber2019",       "stüber|stuber",     2019, "benefit doubt willful ignorance altruistic"),
    ],
}


def get_first_page_text(json_path: Path) -> str:
    try:
        data = json.loads(json_path.read_text(encoding="utf-8"))
    except Exception:
        return ""
    pages = data.get("children") or []
    if not pages:
        return ""
    # First page text
    text_parts = []
    def collect(b):
        for k in ("text", "html"):
            v = b.get(k)
            if isinstance(v, str) and v:
                text_parts.append(v)
        for c in b.get("children") or []:
            collect(c)
    collect(pages[0])
    raw = " ".join(text_parts)
    raw = re.sub(r"<[^>]+>", " ", raw)
    raw = re.sub(r"\s+", " ", raw).strip()
    return raw[:3000].lower()


def main() -> None:
    problems = []
    print(f"{'KEY':25s} {'surname':10s} {'year':6s} {'titleOverlap':12s} VERDICT")
    print("-" * 90)
    for bench, papers in EXPECTED.items():
        for key, surname_alt, year, kw in papers:
            json_path = PROCESSED / bench / key / f"{key}.json"
            if not json_path.exists():
                print(f"{bench}/{key}: MISSING JSON")
                continue
            text = get_first_page_text(json_path)
            surnames = [s.strip() for s in surname_alt.lower().split("|")]
            surname_ok = any(s in text for s in surnames)
            year_ok = str(year) in text
            tokens = [t for t in kw.lower().split() if len(t) >= 4]
            overlap = sum(1 for t in tokens if t in text) / max(len(tokens), 1)
            if surname_ok and year_ok and overlap >= 0.5:
                verdict = "OK"
            elif surname_ok and overlap >= 0.5:
                verdict = "OK (year not on p1)"
            elif overlap >= 0.7:
                verdict = "OK (no surname on p1)"
            else:
                verdict = "⚠ MISMATCH"
                problems.append((bench, key, surname_ok, year_ok, overlap))
            surname_str = "✓" if surname_ok else "✗"
            year_str = "✓" if year_ok else "✗"
            print(f"{bench[:3]}/{key:<20s} {surname_str:8s} {year_str:5s} {overlap:>10.0%}  {verdict}")

    if problems:
        print("\n=== PROBLEMS ===")
        for bench, key, surname_ok, year_ok, overlap in problems:
            print(f"  {bench}/{key}: surname={surname_ok}, year={year_ok}, title-overlap={overlap:.0%}")


if __name__ == "__main__":
    main()
