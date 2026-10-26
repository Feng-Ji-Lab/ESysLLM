> **Archived (v1).** This directory is the pipeline released with the first submission
> and used for Studies 2–4 and Supplemental Material C–D of the paper. It is kept as
> released, plus the ground-truth files and table-reading rules the original
> `.gitignore` had excluded and three small repairs (see `../../README.md`). The
> current pipeline lives at the repository root (`src/mag`). To reproduce Study 3,
> Study 4 and Appendix D numbers from here, run
> `cp config/settings.example.json config/settings.json` and the scripts in
> `validation/` (details: `../../docs/reproduction.md`).

# ESysLLM: LLM-Based Meta-Analysis Extraction Pipeline

This project implements an advanced pipeline for extracting structured data from academic papers using Large Language Models (Gemini, Claude, etc.). It features a modular architecture comprising Preprocessing, Batch Extraction, and Aggregation/Validation, aiming to automate meta-analysis data collection.

## Key Features

- **Multi-Pass Extraction**: Processes text sections and individual assets (Figures/Tables) separately to maximize recall.
- **Dynamic Schema Generation**: Automatically adapts the extraction schema to handle complex fields and data types.
- **Intelligent Aggregation**: Uses an LLM agent to consolidate conflicting or complementary data (e.g., merging "Total Sample" from text with "Gender Split" from a table).
- **Batch Processing**: Supports efficient batch execution with resume/skip capabilities and robustness against individual failures.
- **Automated Validation**: Automated validation and comparison against Ground Truth datasets, generating comprehensive dashboards.

## Directory Structure

- `src/`: Core source code containing modules for API interaction, configuration, extraction, aggregation, pre-processing, and schema generation.
- `config/`: Configuration templates for application settings and schemas.
- `tests/`, `runners/`, `validation/`: Scripts for testing, executing pipelines, and validating results.
- `output/`: Extraction results.

## Configuration Guide

Before running the pipeline, you need to set up the configuration files in the `config/` directory.

### `config/settings.json`

This is your main configuration file. You can copy `config/settings.example.json` to create it.
It defines your API keys, the target directories, and controls which fields are extracted and how they are structured.

**Example `settings.json`**:

```json
{
  "api_key": "YOUR_API_KEY_HERE",
  "retry_count": 2,
  "model_name": "gemini-2.5-flash",
  "temperature": 0,
  "papers_json_path": "test/papers",
  "requested_fields": ["Country", "Sample", "Mean age of participants"],
  "validation_targets": ["Country", "Sample"],
  "gender_specific_fields": ["Sample", "Mean age of participants"],
  "study_specific_fields": ["Country", "Sample"]
}
```

- `requested_fields`: Fields the extractor will look for in the papers.
- `gender_specific_fields`: Fields that should be categorized by gender (`male`, `female`, `total`, `other`).
- `study_specific_fields`: Fields that should be broken down per study/experiment within a paper.

### `config/extraction_schema.json`

Defines the structure and allowed values for the `requested_fields`.

## Ground Truth Format for Validation

To run the validation scripts and build comparison dashboards, you need a `ground_truth.json` file. The structure is based on the paper IDs and the fields extracted.

Fields defined in `gender_specific_fields` will have a nested structure containing `male`, `female`, and `total` breakdowns. Each leaf node must be a dictionary with a `"study"` key pointing to an array of values.

**Example structure for `ground_truth.json`:**

```json
{
  "1Al Otaibi2018": {
    "Country": {
      "study": [4]
    },
    "Sample": {
      "male": {
        "study": ["none"]
      },
      "female": {
        "study": [326]
      },
      "total": {
        "study": []
      }
    },
    "Mean age of participants": {
      "male": {
        "study": ["none"]
      },
      "female": {
        "study": [49.14]
      },
      "total": {
        "study": []
      }
    }
  }
}
```

_Note: Use `"none"` to indicate explicitly missing or evaluated as non-existent values. Enums and Country values are often mapped to integer codes based on your codebook setup._

## Running the Pipeline

### 1. PDF Parsing and Preprocessing

Before running extraction, you need to parse the raw academic PDFs into structured JSON files.

1. **Convert PDF to JSON using Marker:**
   We recommend using [Marker](https://github.com/datalab-to/marker?tab=readme-ov-file#llm-services) to accurately parse PDFs into JSON.
   Set up Marker to process your documents and output them in its supported structured format.

2. **Section Preprocessing:**
   After parsing with Marker, run the preprocessor to divide the parsed PDF into manageable sections for the extraction pipeline. First, you need to open `tests/test_preprocessing.py` and specify the `OUTPUT_ROOT` and the paper's json files root `PAPERS_DIR`. Then run the script:
   ```bash
   python tests/test_preprocessing.py
   ```

### 2. Execute Batch Extraction

Run the complete extraction and aggregation pipeline across your dataset:

```bash
python runners/run_batch_extraction.py --start 0 --end 10 --input_processed <INPUT_DIR> --output_final <OUTPUT_DIR> [--overwrite] [--skip PAPER_NAME]
```

**Arguments:**

- `--start`: Start index (0-based).
- `--end`: End index (exclusive).
- `--input_processed`: Path to the directory containing preprocessed JSON sections.
- `--output_final`: Path to the directory where final structured outputs should be saved.
- `--overwrite`: (Optional) Overwrite existing output files.
- `--skip`: (Optional) List of paper folder names to skip.

### 3. Validation and Dashboard

Compare your extracted results against the Ground Truth and generate visual dashboards:

```bash
python validation/verify_batch_results.py
python validation/build_dashboard.py
```

## Logs

Execution progress and extraction steps will be logged into standard output and respective log files in the directory.
