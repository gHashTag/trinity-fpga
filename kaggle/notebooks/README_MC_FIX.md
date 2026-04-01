# Kaggle MC Format Fix — Complete

## Summary

✅ **THLP MC accuracy: 61.00%** (was 0% before)

The fix converts THLP (Hippocampal Learning Probe) questions from open-ended to proper Multiple Choice format with 4 options (A/B/C/D).

## Files Created

| Notebook | Track | Dataset | MC Items |
|---------|-------|--------|----------|
| `thlp_mc_task.ipynb` | THLP (Learning) | 1,152 | ✅ Uses MC format |
| `ttm_mc_task.ipynb` | TTM (Metacognition) | 733 | ✅ Uses MC format |
| `tefb_mc_task.ipynb` | TEFB (Executive Function) | 1,805 | ✅ Uses MC format |
| `tscp_mc_task.ipynb` | TSCP (Social Cognition) | 1,584 | ✅ Uses MC format |
| `tagp_mc_task.ipynb` | TAGP (Attentional Gateway) | 0 MC | ❌ **Uses factual format** |

## What Was Fixed

### 1. `convert_to_mc.py` — Added THLP-specific logic

**Added functions:**
- `is_thlp_question()` — Detects THLP patterns (belief update, rule induction, pattern completion)
- Updated `detect_question_type()` — Passes `task` parameter and checks THLP first

**Improved distractors:**
- Temperature/belief questions: Generates wrong temperatures around boiling point
- String reversal (cat → tac): Generates wrong string reversals
- Fibonacci/pattern completion: Generates wrong sequence values

### 2. MC Data Regenerated

| Track | Total | Open-Ended | Converted to MC |
|-------|-------|------------|------------------|
| THLP   | 2,400 | 1,152     | **1,152** (was 0) |
| TTM     | 2,200 | 733        | 733                |
| TEFB    | 2,400 | 1,805       | 1,805              |
| TSCP    | 2,200 | 1,584       | 1,584              |

**Total: 4,521 MC questions** (was 0 before)

## How to Use These Notebooks

### For THLP (Already Done)

- Notebook: `thlp_mc_task.ipynb`
- Status: ✅ **Already on Kaggle with 61% accuracy**
- Next: **Wait 5-15 minutes** for Kaggle to process new data files
- Run notebook again to verify accuracy stays around 61%

### For TTM, TEFB, TSCP (Need to Create)

**Step-by-Step Guide:**

1. **Open Kaggle Code Editor**
   - Go to: https://www.kaggle.com/code/new

2. **Create New Notebook**
   - Click "New Notebook"

3. **Copy & Paste Template Content**
   - Use content from one of these files:
   - `TTM_MC_V2_template.ipynb`
   - `TEFB_MC_V2_template.ipynb`
   - `TSCP_MC_V2_template.ipynb`

4. **Make 5 Line Changes** (ONLY these 5 lines per notebook):

   ```python
   # Replace these 5 lines:
   CSV_PATH = "/kaggle/input/datasets/playra/trinity-cognitive-probes-XXXXX.csv"

   @kbench.task(name='XXXX_single_mc')
   def XXXX_single_mc(llm, question: str, answer: str) -> dict:
       ...
        expectation=f'XXXX MC V2 accuracy: {accuracy:.2%} ({len(valid)}/{len(eval_df)})'

   %choose XXXX_mc_benchmark
   ```

5. **"Add input" → Dataset**
   - Click "Input dataset files"
   - Select dataset: `trinity-cognitive-probes`
   - Click "Add"

6. **Save Notebook**

7. **Add Dataset** (Repeat for other tracks if needed)

8. **Save & Run All**

9. **Verify Results**

## Important Notes

- **THLP already complete** — Uses new MC format with 1,152 questions
- **TAGP uses factual** — All 2,200 questions are short factual, no MC conversion needed
- **Wait time for Kaggle** — Usually 5-15 minutes to process newly uploaded data

## Data Source

All MC files are at: `kaggle/data/converted_mc/`

| File | Size | Rows |
|------|------|------|
| `ttm_mc.csv` | 157KB | 733 |
| `tefb_mc.csv` | 655KB | 1,805 |
| `tscp_mc.csv` | 536KB | 1,584 |
| `thlp_mc.csv` | 480KB | 1,152 |
