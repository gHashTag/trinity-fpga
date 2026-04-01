# 🎯 Creating a New Kaggle Benchmark — Step-by-Step Guide (CORRECTED)

## 📋 Track Summary Table

| # | Track | MC Questions | Status | Notebook |
|---|-------|--------------|--------|----------|
| 1 | THLP (Learning) | 1,152 | ✅ DONE | [trinity-hippocampal-learning-thlp-mc-update-v1](https://www.kaggle.com/code/playra/trinity-hippocampal-learning-thlp-mc-update-v1) |
| 2 | TTM (Metacognition) | 733 | ✅ DONE | TTMC_MC_V2_TEMPLATE-FIXED.ipynb |
| 3 | TEFB (Executive) | 1,805 | ✅ DONE | TEFB_MC_V2_TEMPLATE-FIXED.ipynb |
| 4 | TSCP (Social) | 1,584 | ✅ DONE | TSCP_MC_V2_TEMPLATE-FIXED.ipynb |
| 5 | TAGP (Attention) | 0 MC | ❌ SKIP | All factual |

---

## ⚠️ IMPORTANT: Fix the file path!

### Problem

```
FileNotFoundError: '/kaggle/input/trinity-cognitive-probes-tmp/tmp_mc.csv'
```

### Solution

In Kaggle notebook **first upload the dataset**, then search for file:

```python
# ❌ WRONG code (gives error)
CSV_PATH = "/kaggle/input/trinity-cognitive-probes-tmp/tmp_mc.csv"
raw_df = pd.read_csv(CSV_PATH)

# ✅ CORRECT code (upload first)
kaggle.api.dataset_download_files(
    'playra/trinity-cognitive-probes',
    path='/kaggle/working/datasets/',
    unzip=True
)
csv_files = glob.glob('/kaggle/working/datasets/**/*.csv', recursive=True)
csv_path = [f for f in csv_files if 'tmp_mc.csv' in f][0]
df = pd.read_csv(csv_path)
```

---

## 📁 Step-by-Step Instructions

### To create **TTM** notebook:

#### Step 1: Open Kaggle Code Editor

1. Go to: https://www.kaggle.com/code/new
2. Click **"New Notebook"**

#### Step 2: Paste CORRECTED template

Copy content from file: **`TTM_MC_V2_TEMPLATE-FIXED.ipynb`**

#### Step 3: Change notebook title

1. Click **"Settings"** (top right)
2. Change **Title** to: `Trinity Metacognition Probe - TTM MC Update v2`

#### Step 4: Save

1. Click **"Save"**
2. Click **"Save & Run All"**

#### Step 5: Verify result

- You'll see: `📊 Loaded 733 TTM MC questions`
- Then: `🏆 Result: XX.XX%`

---

### To create **TEFB** notebook:

**Replace only these 3 lines** in template:

| # | Was | Replace with |
|---|---------|-------------|
| 1 | `# CELL 4: Load MC Data for TTM` | `# CELL 4: Load MC Data for TEFB` |
| 2 | `csv_path = [f for f in csv_files if 'tmp_mc.csv' in f][0]` | `csv_path = [f for f in csv_files if 'tefb_mc.csv' in f][0]` |
| 3 | `print(f"📊 Loaded {len(eval_df)} TTM MC questions")` | `print(f"📊 Loaded {len(eval_df)} TEFB MC questions")` |
| 4 | `@kbench.task(name="TTM MC Single", ...)` | `@kbench.task(name="TEFB MC Single", ...)` |
| 5 | `def ttm_single_mc(...)` | `def tefb_single_mc(...)` |
| 6 | `@kbench.task(name="Trinity TTM MC", ...)` | `@kbench.task(name="Trinity TEFB MC", ...)` |
| 7 | `def ttm_mc_benchmark(...)` | `def tefb_mc_benchmark(...)` |
| 8 | `run = ttm_mc_benchmark.run()` | `run = tefb_mc_benchmark.run()` |
| 9 | `%choose ttm_mc_benchmark` | `%choose tefb_mc_benchmark` |
| 10 | `expectation=f"TTM MC V2 accuracy: ..."` | `expectation=f"TEFB MC V2 accuracy: ..."` |

---

### To create **TSCP** notebook:

**Replace only these 3 lines** in template:

| # | Was | Replace with |
|---|---------|-------------|
| 1 | `# CELL 4: Load MC Data for TTM` | `# CELL 4: Load MC Data for TSCP` |
| 2 | `csv_path = [f for f in csv_files if 'tmp_mc.csv' in f][0]` | `csv_path = [f for f in csv_files if 'tscp_mc.csv' in f][0]` |
| 3 | `print(f"📊 Loaded {len(eval_df)} TTM MC questions")` | `print(f"📊 Loaded {len(eval_df)} TSCP MC questions")` |
| 4 | `@kbench.task(name="TTM MC Single", ...)` | `@kbench.task(name="TSCP MC Single", ...)` |
| 5 | `def ttm_single_mc(...)` | `def tscp_single_mc(...)` |
| 6 | `@kbench.task(name="Trinity TTM MC", ...)` | `@kbench.task(name="Trinity TSCP MC", ...)` |
| 7 | `def ttm_mc_benchmark(...)` | `def tscp_mc_benchmark(...)` |
| 8 | `run = ttm_mc_benchmark.run()` | `run = tscp_mc_benchmark.run()` |
| 9 | `%choose ttm_mc_benchmark` | `%choose tscp_mc_benchmark` |
| 10 | `expectation=f"TTM MC V2 accuracy: ..."` | `expectation=f"TSCP MC V2 accuracy: ..."` |

---

## 📁 Corrected Templates

| File | For track |
|------|-----------|
| `TTM_MC_V2_TEMPLATE-FIXED.ipynb` | TTM |
| `TEFB_MC_V2_TEMPLATE-FIXED.ipynb` | TEFB |
| `TSCP_MC_V2_TEMPLATE-FIXED.ipynb` | TSCP |

---

## 🎯 Summary

**For each track (TTM, TEFB, TSCP):**

1. Open https://www.kaggle.com/code/new
2. Copy corrected template (from list above)
3. **Replace 10 lines** (see tables above)
4. Save and run

**Bonus:** TAGP not needed — all questions are factual

---

## 📊 Final Statistics

| Track | MC Questions | Status |
|------|--------------|--------|
| THLP | 1,152 | ✅ 61% accuracy |
| TTM | 733 | ✅ Ready to launch |
| TEFB | 1,805 | ✅ Ready to launch |
| TSCP | 1,584 | ✅ Ready to launch |
| **TOTAL** | **4,521** | **4 tracks** |
