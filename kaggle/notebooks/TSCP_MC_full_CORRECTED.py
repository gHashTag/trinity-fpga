# ================================================
# Trinity TSCP MC — Kaggle Benchmark Task (v2, full) — ИСПРАВЛЕННЫЙ
# ================================================

import kaggle_benchmarks as kbench
import pandas as pd

print('Ready to benchmark TSCP MC (full run)')

# ---------- 1. Load data ----------
CSV_PATH = "/kaggle/input/datasets/playra/trinity-cognitive-probes/tscp_social.csv"

raw_df = pd.read_csv(CSV_PATH)
print(f'Loaded {len(raw_df)} TSCP rows')
print("Columns:", raw_df.columns.tolist())
print(raw_df.head(5))

# TSCP использует scenario/expected_inference, а не question/answer
df = raw_df[["scenario", "expected_inference"]]

print("\nEvaluation frame (sample):")
print(df.head(5))

# ---------- 2. Single task ----------
@kbench.task(name='tscp_single_mc')
def tscp_single_mc(llm, scenario: str, expected_inference: str) -> dict:
    prompt = f'''{scenario}

Answer as briefly as possible in a few words.'''

    resp = llm.prompt(prompt)
    text = str(resp).strip()

    got = text.lower().strip()
    exp = str(expected_inference).lower().strip()
    is_correct = (exp in got) or (got == exp)

    return {'correct': is_correct, 'got': text, 'exp': expected_inference}

# ---------- 3. Benchmark ----------
@kbench.task(name='tscp_mc_benchmark')
def tscp_mc_benchmark(llm, data: pd.DataFrame) -> float:
    with kbench.client.enable_cache():
        runs = tscp_single_mc.evaluate(
            llm=[llm],
            evaluation_data=data,
            n_jobs=2,
            timeout=180,
            max_attempts=1,
            remove_run_files=True,
        )

    eval_df = runs.as_dataframe()
    accuracy = float(
        eval_df["result"]
        .apply(lambda d: bool(d.get("correct", False)))
        .mean()
    )

    kbench.assertions.assert_true(
        True,
        expectation=f'TSCP MC accuracy: {accuracy:.2%} ({len(eval_df)}/{len(data)})'
    )

    return accuracy

# ---------- 4. RUN (full df) ----------
run = tscp_mc_benchmark.run(kbench.llm, df)
print(f'\n🏆 TSCP MC Accuracy: {run.result:.2%}')
%choose tscp_mc_benchmark
