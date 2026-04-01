# ================================================
# Trinity TTM MC — Kaggle Benchmark Task (v2, full)
# ================================================

import kaggle_benchmarks as kbench
import pandas as pd

print('Ready to benchmark TTM MC (full run)')

# ---------- 1. Load data ----------
CSV_PATH = "/kaggle/input/datasets/playra/trinity-cognitive-probes/tmp_mc.csv"

raw_df = pd.read_csv(CSV_PATH)
print(f'Loaded {len(raw_df)} TTM MC rows')
print("Columns:", raw_df.columns.tolist())
print(raw_df.head(5))

df = raw_df[["question", "answer"]]

print("\nEvaluation frame (sample):")
print(df.head(5))

# ---------- 2. Single task ----------
@kbench.task(name='ttm_single_mc')
def ttm_single_mc(llm, question: str, answer: str) -> dict:
    prompt = f'''{question}

Answer as briefly as possible in a few words.'''

    resp = llm.prompt(prompt)
    text = str(resp).strip()

    got = text.lower().strip()
    exp = str(answer).lower().strip()
    is_correct = (exp in got) or (got == exp)

    return {'correct': is_correct, 'got': text, 'exp': answer}

# ---------- 3. Benchmark ----------
@kbench.task(name='ttm_mc_benchmark')
def ttm_mc_benchmark(llm, data: pd.DataFrame) -> float:
    with kbench.client.enable_cache():
        runs = ttm_single_mc.evaluate(
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
        expectation=f'TTM MC accuracy: {accuracy:.2%} ({len(eval_df)}/{len(data)})'
    )

    return accuracy

# ---------- 4. RUN (full df) ----------
run = ttm_mc_benchmark.run(kbench.llm, df)
print(f'\n🏆 TTM MC Accuracy: {run.result:.2%}')
%choose ttm_mc_benchmark
