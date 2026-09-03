#!/usr/bin/env python3
"""
GF8-абляция на RunPod — v2 (18.07.2026). Автофиксы против падений v1:
  1. Blackwell sm_120: авто-переустановка torch cu128, если текущий torch без ядер под GPU.
  2. nproc_per_node = реальное число GPU (v1 жёстко требовал 8).
  3. FA3 (Hopper-only) → каскад FA3→FA2→SDPA внутри train_gpt_cuda_gf8.py.
  4. Полный env-блок официальной записи Ifrim + оверрайды под один GPU.
  5. Полные логи в файлы + вывод хвоста и Traceback при падении (v1 резал до 500 символов).

Запуск:  curl -s https://raw.githubusercontent.com/gHashTag/trinity-fpga/main/run_gf8_on_runpod.py | python3
Оверрайды: ABLATE_ITERATIONS (деф. 2000), ABLATE_BATCH_TOKENS (деф. 65536), ABLATE_ARMS="fp8,fp8s,gf8"

Метрика: final_ternary_roundtrip val_bpb — проходит полный roundtrip сериализации,
включая fp8/gf8-карманы. Три плеча: fp8 (репро, прямой cast e4m3), fp8s (e4m3 +
per-row scale — контроль), gf8 (e3m4 φ-правило + per-row scale). Δ(gf8−fp8s) = чистый
эффект формата; Δ(fp8s−fp8) = эффект масштабирования.
ВАЖНО: обёртка НЕ импортирует torch (иначе его нельзя переустановить на лету).
"""
import subprocess, os, json, re, sys, glob, time

RAW = "https://raw.githubusercontent.com/gHashTag/trinity-fpga/main/parameter_golf_gf8_ablation"
WORK = "/workspace/pg/parameter-golf"


def sh(cmd, timeout=None, tail=400):
    print(f"$ {cmd[:140]}{'...' if len(cmd) > 140 else ''}", flush=True)
    r = subprocess.run(cmd, shell=True, timeout=timeout, capture_output=True, text=True)
    out = (r.stdout or "") + (r.stderr or "")
    if tail and out.strip():
        print(out[-tail:], flush=True)
    return r.returncode, out


# --- 1. GPU ---
rc, out = sh("nvidia-smi -L")
ngpu = len([l for l in out.splitlines() if l.startswith("GPU ")])
assert ngpu >= 1, "GPU не найден (nvidia-smi -L пуст)"
rc, cap = sh("nvidia-smi --query-gpu=compute_cap --format=csv,noheader", tail=0)
sm = "sm_" + cap.strip().splitlines()[0].strip().replace(".", "")
print(f"\nGPUs: {ngpu}, арх: {sm}")

# --- 2. torch с ядрами под эту архитектуру ---
rc, arch = sh('python3 -c "import torch; print(torch.cuda.get_arch_list())"', tail=0)
if rc != 0 or sm not in arch:
    print(f"\n=== torch без {sm} — ставлю torch cu128 (3-6 мин) ===")
    sh("pip3 install -q -U torch --index-url https://download.pytorch.org/whl/cu128", timeout=1800, tail=200)
    rc, arch = sh('python3 -c "import torch; print(torch.__version__, torch.cuda.get_arch_list())"', tail=0)
    print(arch.strip()[-200:])
    assert rc == 0 and sm in arch, f"torch всё ещё без {sm} — останов. Вывод: {arch[-300:]}"

# --- 3. deps (FA3 опционален: без него train сам уйдёт в SDPA) ---
print("\n=== Deps ===")
sh("pip3 install -q sentencepiece numpy 'huggingface_hub[cli]'", timeout=900, tail=100)
sh('python3 -c "import flash_attn_interface" 2>/dev/null || '
   'pip3 install -q --no-cache-dir https://download.pytorch.org/whl/cu128/flash_attn_3-3.0.0-cp39-abi3-manylinux_2_28_x86_64.whl || '
   'echo "FA3 не встал — не страшно, будет SDPA"', timeout=900, tail=150)

# --- 4. файлы абляции ---
os.makedirs(WORK, exist_ok=True)
os.chdir(WORK)
for f in ["gf8_quant.py", "train_gpt_cuda_gf8.py"]:
    sh(f"curl -sfL {RAW}/{f} -o {f}", tail=0)
    assert os.path.exists(f) and os.path.getsize(f) > 1000, f"{f} не скачался из {RAW}"
print("Файлы абляции на месте.")

# --- 5. данные: 1-2 train-шарда + val + токенизатор ---
hf = "hf download" if sh("hf version", tail=0)[0] == 0 else "huggingface-cli download"
if not glob.glob("data/datasets/fineweb10B_sp8192/fineweb_val_*.bin"):
    print("\n=== Данные (HF sproos/parameter-golf-tokenizers) ===")
    sh(f'{hf} sproos/parameter-golf-tokenizers '
       f'--include "datasets/fineweb10B_sp8192/fineweb_val_*" '
       f'"datasets/fineweb10B_sp8192/fineweb_train_00000?*" "tokenizers/*" --local-dir ./data',
       timeout=2400, tail=200)
if not glob.glob("data/datasets/fineweb10B_sp8192/fineweb_train_*.bin"):
    print("Узкий паттерн не совпал — качаю каталог целиком (дольше)")
    sh(f'{hf} sproos/parameter-golf-tokenizers --include "datasets/fineweb10B_sp8192/*" "tokenizers/*" '
       f'--local-dir ./data', timeout=5400, tail=200)
n_train = len(glob.glob("data/datasets/fineweb10B_sp8192/fineweb_train_*.bin"))
n_val = len(glob.glob("data/datasets/fineweb10B_sp8192/fineweb_val_*.bin"))
tok_ok = os.path.exists("data/tokenizers/fineweb_8192_bpe.model")
print(f"train-шардов: {n_train}, val-шардов: {n_val}, токенизатор: {tok_ok}")
assert n_train and n_val and tok_ok, "данные не скачались полностью"

# --- 6. env: полный блок официальной записи + оверрайды под этот под ---
ENV = dict(
    DATA_PATH="./data/datasets/fineweb10B_sp8192", TOKENIZER_PATH="./data/tokenizers/fineweb_8192_bpe.model",
    ATTN_PROJ_TYPE="standard", LOGIT_HEAD_TYPE="standard", TVERSKY_MEMBERSHIP="sigmoid",
    TVERSKY_NUM_FEATURES="0", TVERSKY_FEATURE_POOLS="0", VOCAB_SIZE="8192", BITNET_GROUP_SIZE="128",
    BIGRAM_HASH="0", EMBED_DIM="254", TRAINING_DEPTH_RECURRENCE="0", EVAL_DEPTH_RECURRENCE="0",
    NUM_LAYERS="10", MODEL_DIM="768", NUM_KV_HEADS="4", NUM_HEADS="8", DIFF_ATTN="0", MLP_MULT="4",
    MLP_GROUPS="0", MATRIX_OPTIMIZER="muon", ADAM_LR="0.05", ADAM_WD="0.05", MUON_BACKEND_STEPS="3",
    MUON_MOMENTUM="0.95", MUON_MOMENTUM_WARMUP_START="0.85", MUON_MOMENTUM_WARMUP_STEPS="500",
    MUON_WD="0.0", MATRIX_LR="0.04", SCALAR_LR="0.02", TIED_EMBED_LR="0.02", WARMDOWN_FRACTION="0.2",
    LOGIT_SOFTCAP="10", QK_GAIN_INIT="2.25", ROPE_TYPE="yarn", YARN_MAX_LEN="2048", ROPE_BASE="5000",
    BATCH_TOKENS_START="0", BATCH_SCHEDULE_FRACTION="0.33", SEQ_LEN_START="0",
    SEQ_SCHEDULE_FRACTION="0.0", TRAIN_SEQ_LEN="1024", SMEAR="0", WARMUP_STEPS="5",
    TIE_EMBEDDINGS="1", UNTIE_AT_FRACTION="0.00", HEAD_LR="0.02", CORR_WEIGHT_LR="0.02",
    ACTIVATION="relu2", SOFTCAP_TYPE="poly", MTP_HEADS="0", REFINER="0", REFINER_KERNEL="3",
    TEMP_SCALING="0", COMPILE_MODE="default", OMP_NUM_THREADS="1",
    # --- оверрайды под слабый под (одинаковы для ВСЕХ плеч => сравнение честное) ---
    TRAIN_BATCH_TOKENS=os.environ.get("ABLATE_BATCH_TOKENS", "65536"),
    VAL_BATCH_SIZE="65536",
    ITERATIONS=os.environ.get("ABLATE_ITERATIONS", "2000"),
    MAX_WALLCLOCK_SECONDS="100000",   # фиксируем ШАГИ, не время (иначе медленное плечо получит меньше шагов)
    VAL_MAX_TOKENS="2000000",
    VAL_LOSS_EVERY="0", TRAIN_LOG_EVERY="200", CHURN_LOG_EVERY="0",
    SLIDING_EVAL="0",                  # метрика = final_ternary_roundtrip (быстрее и включает roundtrip карманов)
    SLIDING_EVAL_STRIDE="16", SLIDING_BATCH_SIZE="64",
)

arms = [a.strip() for a in os.environ.get("ABLATE_ARMS", "fp8,fp8s,gf8").split(",") if a.strip()]
FPS = {"fp8": "FP8", "fp8s": "FP8S", "gf8": "GF8"}
results = {}

for arm in arms:
    print(f"\n{'=' * 60}\n=== ПЛЕЧО: {arm} (FP_STORAGE={FPS[arm]}, seed=1337, steps={ENV['ITERATIONS']}) ===\n{'=' * 60}", flush=True)
    env = dict(os.environ); env.update(ENV)
    env["FP_STORAGE"] = FPS[arm]; env["SEED"] = "1337"; env["RUN_ID"] = f"ablate_{arm}"
    log_path = f"/workspace/log_ablate_{arm}.txt"
    t0 = time.time()
    with open(log_path, "w") as lf:
        p = subprocess.run(f"torchrun --standalone --nproc_per_node={ngpu} train_gpt_cuda_gf8.py",
                           shell=True, env=env, stdout=lf, stderr=subprocess.STDOUT, timeout=10800)
    out = open(log_path).read()
    m = re.findall(r"final_ternary_roundtrip val_loss:([\d.]+) val_bpb:([\d.]+)", out)
    back = re.findall(r"\[attn\] backend = (\w+)", out)
    print(f"время: {time.time() - t0:.0f}s, attn={back[0] if back else '?'}, rc={p.returncode}")
    if p.returncode != 0 or not m:
        print(f"  ПАДЕНИЕ. Хвост лога ({log_path}):\n{out[-4000:]}")
        tb = re.findall(r"Traceback[\s\S]{0,2000}?(?=\n\S|\Z)", out)
        if tb:
            print("\n--- Первый Traceback ---\n" + tb[0])
        continue
    results[arm] = float(m[-1][1])
    print(f"  {arm}: final_roundtrip val_bpb = {results[arm]:.4f}")

# --- отчёт ---
print(f"\n{'=' * 60}\nGF8 ABLATION RESULTS (seed=1337, steps={ENV['ITERATIONS']}, batch={ENV['TRAIN_BATCH_TOKENS']})\n{'=' * 60}")
print(f"{'Плечо':<10} {'val_bpb':>10}")
for arm, bpb in sorted(results.items(), key=lambda x: x[1]):
    print(f"{arm:<10} {bpb:>10.4f}")
if "gf8" in results and "fp8s" in results:
    print(f"\nΔ формата (gf8 − fp8s): {results['gf8'] - results['fp8s']:+.4f} BPB")
if "fp8s" in results and "fp8" in results:
    print(f"Δ масштабирования (fp8s − fp8): {results['fp8s'] - results['fp8']:+.4f} BPB")
print("\nЧестность: 1 сид => |Δ| < ~0.003 BPB не значимо; для вывода нужно 3 сида "
      "(протокол Parameter Golf) и Δ ≥ 0.005. Абсолютные bpb НЕ сравнимы с официальными "
      "(другой батч/шаги/GPU) — сравнивать только плечи между собой.")
json.dump({"results": results, "iterations": ENV["ITERATIONS"], "batch_tokens": ENV["TRAIN_BATCH_TOKENS"],
           "ngpu": ngpu, "sm": sm, "seed": 1337},
          open("/workspace/gf8_results.json", "w"), indent=2)
print("\nSaved: /workspace/gf8_results.json\nDONE")
