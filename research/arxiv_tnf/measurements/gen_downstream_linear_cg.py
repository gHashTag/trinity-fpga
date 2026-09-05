#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Вторая downstream-задача TNF: итерационное решение линейной системы.

Решается SPD-система A x=b в сырых масштабах без нормировки методом
сопряжённых градиентов. Все скалярные произведения на кандидатах суммируются
в float32; float64 используется только как эталон. Результат — ошибка решения
и число итераций до заданного остатка, а не SQNR представления.
"""
import json, math, os, sys
from fractions import Fraction
import numpy as np

sys.path.insert(0, '/tmp/tfpga/conformance')
import tnf_ref as TNF
import takum_ref as TAK

SEED = 20260814
# Необусловленная, но положительно определённая система: коэффициенты
# намеренно не являются чистыми степенями двойки, чтобы формат влиял на
# результат задачи, а не только на запись точных тестовых значений.
# Коэффициенты охватывают около 17 двоичных порядков и содержат
# неидеальные значащие части; это оставляет fp32-аккумулятор общим
# знаменателем, но не превращает все входы в точные степени двойки.
A64 = np.array([[1.234567 * 2.0**10, 0.317 * 2.0**-2],
                [0.317 * 2.0**-2, 1.999 * 2.0**-7]], dtype=np.float64)
X_TRUE = np.array([1.2345, -2.3456], dtype=np.float64)
B64 = A64 @ X_TRUE
MAX_ITERS = 80
TOL = 1e-6


def qcast(fmt, x):
    x = float(x)
    if fmt is None:
        return x
    if not math.isfinite(x):
        return x
    raw = TNF.encode(fmt, Fraction(x)) if isinstance(fmt, TNF.TNFFormat) else TAK.encode(fmt, Fraction(x))
    d = TNF.decode(fmt, raw) if isinstance(fmt, TNF.TNFFormat) else TAK.decode(fmt, raw)
    if isinstance(d, TAK.Special) or (isinstance(d, float) and not math.isfinite(d)):
        return float('nan')
    return float(d)


def qadd(fmt, a, b): return qcast(fmt, float(a) + float(b))
def qsub(fmt, a, b): return qcast(fmt, float(a) - float(b))
def qmul(fmt, a, b): return qcast(fmt, float(a) * float(b))
def qdiv(fmt, a, b): return qcast(fmt, float(a) / float(b))


def dot(fmt, a, b):
    # Binding requirement: fp32 accumulator for every non-reference candidate.
    if fmt is None:
        acc = np.float64(0.0)
        for ai, bi in zip(a, b): acc = np.float64(acc + np.float64(ai) * np.float64(bi))
        return float(acc)
    acc = np.float32(0.0)
    for ai, bi in zip(a, b):
        # Product is formed in the accumulator domain; only the reduction
        # state is stored in fp32. Quantising the product back to 16 bits
        # would test multiplier overflow, not fp32 accumulation.
        acc = np.float32(acc + np.float32(ai) * np.float32(bi))
    return float(acc)


def matvec(fmt, A, x):
    out = []
    for row in A:
        if fmt is None:
            out.append(dot(None, row, x))
        else:
            # Each row reduction has the mandatory fp32 accumulator.
            acc = np.float32(0.0)
            for ai, xi in zip(row, x):
                acc = np.float32(acc + np.float32(ai) * np.float32(xi))
            out.append(float(acc))
    return out


def solve(fmt):
    A = [[qcast(fmt, A64[i,j]) for j in range(2)] for i in range(2)] if fmt is not None else A64.tolist()
    b = [qcast(fmt, v) for v in B64] if fmt is not None else B64.tolist()
    x = [qcast(fmt, 0.0), qcast(fmt, 0.0)]
    r = [qsub(fmt, bi, ai) for bi, ai in zip(b, matvec(fmt, A, x))]
    p = list(r)
    rr = dot(fmt, r, r)
    r0 = rr
    history = []
    converged = None
    for it in range(1, MAX_ITERS + 1):
        Ap = matvec(fmt, A, p)
        denom = dot(fmt, p, Ap)
        if not math.isfinite(denom) or denom == 0.0 or not all(math.isfinite(v) for v in Ap):
            break
        alpha = qdiv(fmt, rr, denom)
        x = [qadd(fmt, xi, qmul(fmt, alpha, pi)) for xi, pi in zip(x, p)]
        r_new = [qsub(fmt, ri, qmul(fmt, alpha, api)) for ri, api in zip(r, Ap)]
        rr_new = dot(fmt, r_new, r_new)
        rel = math.sqrt(abs(rr_new) / abs(r0)) if r0 else 0.0
        history.append({'iteration': it, 'relative_residual': rel})
        if converged is None and rel <= TOL:
            converged = it
        if rr_new == 0.0:
            r, rr = r_new, rr_new
            break
        beta = qdiv(fmt, rr_new, rr)
        p = [qadd(fmt, rni, qmul(fmt, beta, pi)) for rni, pi in zip(r_new, p)]
        r, rr = r_new, rr_new
    x_arr = np.array(x, dtype=np.float64)
    residual = A64 @ x_arr - B64
    return {
        'x_hat': [float(v) for v in x_arr],
        'relative_solution_error': float(np.linalg.norm(x_arr - X_TRUE) / np.linalg.norm(X_TRUE)),
        'relative_residual_64': float(np.linalg.norm(residual) / np.linalg.norm(B64)),
        'iterations_to_relative_residual_1e-6': converged,
        'iterations_run': len(history),
        'final_relative_residual': history[-1]['relative_residual'] if history else None,
        'history': history,
    }


def main():
    candidates = {
        'float64_reference': None,
        'binary16': 'binary16',
        'TNF16_(4,8)': TNF.TNFFormat(4,8),
        'takum16': TAK.TakumFormat('takum16', 16),
    }
    out = {
        'task': 'Итерационное решение SPD-системы 2x2 методом сопряжённых градиентов в сырых масштабах без нормировки',
        'seed': SEED,
        'A_SI': A64.tolist(),
        'x_true': X_TRUE.tolist(),
        'b_SI': B64.tolist(),
        'tolerance_relative_residual': TOL,
        'max_iterations': MAX_ITERS,
        'accumulator': 'float32 for binary16/TNF16/takum16; float64 only for reference',
        'results': {},
    }
    for name, fmt in candidates.items():
        if name == 'binary16':
            # Explicit binary16 path: same algorithm, binary16 storage/ops and
            # fp32 dot accumulator (the binding comparison convention).
            class Binary16:
                pass
            # qcast-compatible local implementation by running a small adapter below.
            old_qcast = globals()['qcast']
            old_qadd = globals()['qadd']
            old_qsub = globals()['qsub']
            old_qmul = globals()['qmul']
            old_qdiv = globals()['qdiv']
            def bqcast(_fmt, x):
                return float(np.float16(x))
            def bqadd(_fmt,a,b): return bqcast(_fmt,float(a)+float(b))
            def bqsub(_fmt,a,b): return bqcast(_fmt,float(a)-float(b))
            def bqmul(_fmt,a,b): return bqcast(_fmt,float(a)*float(b))
            def bqdiv(_fmt,a,b): return bqcast(_fmt,float(a)/float(b))
            globals()['qcast'], globals()['qadd'], globals()['qsub'], globals()['qmul'], globals()['qdiv'] = bqcast,bqadd,bqsub,bqmul,bqdiv
            out['results'][name] = solve(object())
            globals()['qcast'], globals()['qadd'], globals()['qsub'], globals()['qmul'], globals()['qdiv'] = old_qcast,old_qadd,old_qsub,old_qmul,old_qdiv
        else:
            out['results'][name] = solve(fmt)
        out['results'][name].pop('history', None)
    # Reproducibility block: everything a third party needs to obtain the same
    # numbers, recorded inside the artefact rather than in prose about it.
    import hashlib, platform, subprocess
    def _sha(p):
        try:
            return hashlib.sha256(open(p, 'rb').read()).hexdigest()
        except Exception:
            return None
    here = os.path.dirname(os.path.abspath(__file__))
    root = os.path.abspath(os.path.join(here, '..', '..', '..'))
    try:
        head = subprocess.run(['git', '-C', root, 'rev-parse', 'HEAD'],
                              capture_output=True, text=True, timeout=20).stdout.strip()
    except Exception:
        head = None
    out['reproduction'] = {
        'command': 'python3 research/arxiv_tnf/measurements/gen_downstream_linear_cg.py',
        'cwd': 'repository root (gHashTag/trinity-fpga)',
        'git_head': head,
        'python': platform.python_version(),
        'numpy': np.__version__,
        'platform': platform.platform(),
        'stopping_rule': ('loop stops when the stored residual reaches exactly zero, '
                          'when the stored curvature denominator ceases to be finite '
                          'and non-zero, or at max_iterations; the relative-residual '
                          'tolerance is recorded but does not terminate the loop'),
        'x0': [0.0, 0.0],
        'error_metric': 'relative_solution_error = ||x_hat - x_true||_2 / ||x_true||_2, recomputed in float64',
        'residual_metric': 'relative_residual_64 = ||A64 x_hat - b64||_2 / ||b64||_2, recomputed in float64 from unrounded A and b',
        'tnf_parameters': {'E_t': 4, 'M': 8, 'note': 'physical-cell budget rung, not the reconciled TNF16 (4,11)'},
        'takum16_reference': 'conformance/takum_ref.py, TakumFormat("takum16", 16)',
        'oracle_sha256': {
            'conformance/tnf_ref.py': _sha(os.path.join(root, 'conformance', 'tnf_ref.py')),
            'conformance/takum_ref.py': _sha(os.path.join(root, 'conformance', 'takum_ref.py')),
            'this_generator': _sha(os.path.abspath(__file__)),
        },
    }
    # The hash cannot include its own field without becoming circular.  Name
    # the hashed object explicitly: it is the canonical payload before the
    # digest field is appended.
    canonical_payload = json.dumps(out, ensure_ascii=False, indent=2, sort_keys=True)
    out['artefact_sha256_of_canonical_payload'] = hashlib.sha256(
        canonical_payload.encode('utf-8')
    ).hexdigest()
    for path in (os.path.join(here, 'tnf_downstream_linear_cg_2026-08-14.json'),
                 '/home/user/workspace/wave_audit/tnf_downstream_linear_cg_2026-08-14.json'):
        try:
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(out, f, ensure_ascii=False, indent=2, sort_keys=True)
            print('saved', path)
        except Exception as e:
            print('could not save', path, e)
    print(json.dumps(out, ensure_ascii=False, indent=2, sort_keys=True))
    print('canonical payload sha256', out['artefact_sha256_of_canonical_payload'])

if __name__ == '__main__': main()
