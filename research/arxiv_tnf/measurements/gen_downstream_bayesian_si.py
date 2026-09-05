#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Downstream task D: Bayesian estimation of a gravitational parameter in SI.

The task sums Gaussian log-likelihood terms for observations of a = mu/r^2,
where r is in metres, a in m/s^2 and mu in m^3/s^2. Values are deliberately not
normalised: the inverse-square kernel is evaluated in raw SI. TNF/takum quantise
operands and intermediates; the likelihood sum is always a float32 accumulator.
The reference is float64. This is a task-level convergence test, not a claim
about a real instrument data set: observations are a deterministic perturbation
of the Newtonian model so the numerical task is fully reproducible.
"""
import json, math, os, sys
from fractions import Fraction
import numpy as np

sys.path.insert(0, '/tmp/tfpga/conformance')
import tnf_ref as TNF
import takum_ref as TAK

SEED = 20260813
N = 66
MU_TRUE = 1.32712440018e20  # solar gravitational parameter, m^3/s^2
R_MIN_EXP = 50.0
R_MAX_EXP = 59.0

# Deterministic SI data: radii span raw 2^50..2^59 metres; perturbations are
# fixed, not random, so every task-level result is exactly reproducible.
radii = np.array([2.0 ** (R_MIN_EXP + (R_MAX_EXP-R_MIN_EXP)*i/(N-1))
                  for i in range(N)], dtype=np.float64)
phase = np.arange(N, dtype=np.float64)
mu_true_arr = MU_TRUE * np.ones(N)
acc_true = MU_TRUE / (radii * radii)
rel = 0.0030*np.sin(phase*0.71) + 0.0015*np.cos(phase*0.19)
obs = acc_true * (1.0 + rel)
sigma = 0.005 * acc_true  # known 0.5% relative uncertainty in m/s^2

MU0 = MU_TRUE
TH0 = math.log(MU0)


def _finite(x):
    return isinstance(x, (int,float,np.floating)) and math.isfinite(float(x))


def qcast(fmt, x):
    x = float(x)
    if fmt is None:
        return x
    if not math.isfinite(x):
        return x
    raw = TNF.encode(fmt, Fraction(x)) if isinstance(fmt, TNF.TNFFormat) else TAK.encode(fmt, Fraction(x))
    d = TNF.decode(fmt, raw) if isinstance(fmt, TNF.TNFFormat) else TAK.decode(fmt, raw)
    if isinstance(d, TAK.Special) or isinstance(d, float) and not math.isfinite(d):
        return float('nan')
    return float(d)


def qop(fmt, op, a, b=None):
    if op == 'neg': return qcast(fmt, -float(a))
    if op == 'exp': return qcast(fmt, math.exp(float(a)))
    if op == 'log': return qcast(fmt, math.log(float(a)))
    if op == 'add': return qcast(fmt, float(a)+float(b))
    if op == 'sub': return qcast(fmt, float(a)-float(b))
    if op == 'mul': return qcast(fmt, float(a)*float(b))
    if op == 'div': return qcast(fmt, float(a)/float(b))
    raise ValueError(op)


def prepare(fmt):
    if fmt is None:
        return [(float(r), float(y), float(s)) for r,y,s in zip(radii,obs,sigma)]
    out=[]
    for r,y,s in zip(radii,obs,sigma):
        rq=qcast(fmt,r); yq=qcast(fmt,y); sq=qcast(fmt,s)
        r2=qop(fmt,'mul',rq,rq)
        h=qop(fmt,'div',1.0,r2)
        out.append((h,yq,sq))
    return out


def logpost(theta, mode, prepared):
    # theta is evaluated in float64 for the search coordinate; mu and every
    # task operation are quantised in the candidate format.
    fmt = mode.get('fmt')
    mu = qop(fmt,'exp',theta) if fmt is not None else math.exp(theta)
    if not _finite(mu): return -float('inf')
    if fmt is None:
        acc = np.float64(0.0)
    else:
        # Binding requirement: fp32 accumulator for every candidate format.
        acc = np.float32(0.0)
    for h,y,s in prepared:
        if fmt is None:
            pred = mu / (radii[len([])] if False else 1.0)  # not used; h prepared below
            # prepared carries h for consistency, and raw reference computes it exactly here.
            # Recompute from paired raw arrays by index in caller path instead.
            raise RuntimeError('reference path should use logpost_ref')
        pred=qop(fmt,'mul',mu,h)
        resid=qop(fmt,'sub',y,pred)
        z=qop(fmt,'div',resid,s)
        z2=qop(fmt,'mul',z,z)
        t=qop(fmt,'sub',qop(fmt,'mul',-0.5,z2),qop(fmt,'log',s))
        acc = np.float32(acc + np.float32(t))
    # weak normal prior on log(mu), quantised as a task term but accumulated fp32
    prior = qop(fmt,'mul',-0.5, qop(fmt,'mul', qop(fmt,'div', qop(fmt,'sub',theta,TH0), 5.0), qop(fmt,'div', qop(fmt,'sub',theta,TH0), 5.0)))
    acc = np.float32(acc + np.float32(prior))
    return float(acc)


def logpost_ref(theta):
    mu=math.exp(theta)
    acc=np.float64(0.0)
    for r,y,s in zip(radii,obs,sigma):
        h=1.0/(r*r)
        pred=mu*h
        z=(y-pred)/s
        acc=np.float64(acc + (-0.5*z*z - math.log(s)))
    d=(theta-TH0)/5.0
    acc=np.float64(acc - 0.5*d*d)
    return float(acc)


def golden(mode, prepared=None, iterations=72):
    lo,hi=TH0-2.0,TH0+2.0
    phi=(math.sqrt(5.0)-1.0)/2.0
    c=hi-phi*(hi-lo); d=lo+phi*(hi-lo)
    fc=logpost_ref(c) if mode['name']=='ref64' else logpost(c,mode,prepared)
    fd=logpost_ref(d) if mode['name']=='ref64' else logpost(d,mode,prepared)
    history=[]
    for it in range(1,iterations+1):
        if fc < fd:
            lo=c; c=d; fc=fd; d=lo+phi*(hi-lo)
            fd=logpost_ref(d) if mode['name']=='ref64' else logpost(d,mode,prepared)
        else:
            hi=d; d=c; fd=fc; c=hi-phi*(hi-lo)
            fc=logpost_ref(c) if mode['name']=='ref64' else logpost(c,mode,prepared)
        x=(lo+hi)/2
        history.append({'iteration':it,'theta':x,'mu':math.exp(x),'bracket_width':hi-lo,'objective':max(fc,fd)})
    x=(lo+hi)/2
    return {'mu_hat':math.exp(x),'theta_hat':x,'iterations':iterations,
            'bracket_width':hi-lo,'objective':(logpost_ref(x) if mode['name']=='ref64' else logpost(x,mode,prepared)),
            'history':history}


def err(a,b):
    return abs(a-b)/abs(b)


def main():
    candidates=[
        {'name':'ref64','fmt':None},
        {'name':'tnf32','fmt':TNF.TNFFormat(5,23)},
        {'name':'takum32','fmt':TAK.TakumFormat('takum32',32)},
        {'name':'binary32','fmt':None},
    ]
    results={}
    ref=golden(candidates[0], iterations=72)
    results['ref64']=ref
    # binary32 is a separate explicit baseline: quantise all operations through
    # numpy float32 but keep the same fp32 accumulator.
    def run_binary32():
        prep=[(np.float32(1.0/np.float32(r*r)),np.float32(y),np.float32(s)) for r,y,s in zip(radii,obs,sigma)]
        def f(theta):
            mu=np.float32(math.exp(theta)); acc=np.float32(0)
            for h,y,s in prep:
                pred=np.float32(mu*h); z=np.float32((y-pred)/s)
                t=np.float32(-0.5*z*z - np.float32(math.log(float(s))))
                acc=np.float32(acc+ t)
            d=np.float32((theta-TH0)/5.0); acc=np.float32(acc - np.float32(0.5*d*d))
            return float(acc)
        old=logpost
        # local golden implementation
        lo,hi=TH0-2,TH0+2; phi=(math.sqrt(5)-1)/2
        c=hi-phi*(hi-lo); d=lo+phi*(hi-lo); fc=f(c); fd=f(d)
        hist=[]
        for it in range(1,73):
            if fc<fd: lo,c,fc=c,d,fd; d=lo+phi*(hi-lo); fd=f(d)
            else: hi,d,fd=d,c,fc; c=hi-phi*(hi-lo); fc=f(c)
            x_i=(lo+hi)/2
            hist.append({'iteration':it,'mu':math.exp(x_i)})
        x=(lo+hi)/2
        return {'mu_hat':math.exp(x),'theta_hat':x,'iterations':72,'bracket_width':hi-lo,'objective':f(x),'history':hist}
    results['binary32']=run_binary32()
    for name,fmt in [('tnf32',TNF.TNFFormat(5,23)),('takum32',TAK.TakumFormat('takum32',32))]:
        prep=prepare(fmt)
        results[name]=golden({'name':name,'fmt':fmt}, prep, 72)
    for name,r in results.items():
        final_mu = r['mu_hat']
        r['iterations_to_rel_mu_1e-6'] = next(
            (h['iteration'] for h in r.get('history', [])
             if abs(h['mu']-final_mu)/abs(final_mu) <= 1e-6),
            None)
        r['iterations_to_rel_mu_1e-5'] = next(
            (h['iteration'] for h in r.get('history', [])
             if abs(h['mu']-final_mu)/abs(final_mu) <= 1e-5),
            None)
        r['relative_mu_error_vs_ref64']=err(r['mu_hat'],ref['mu_hat'])
        r['relative_mu_error_vs_true']=err(r['mu_hat'],MU_TRUE)
        r['objective_error_vs_ref64']=abs(r['objective']-ref['objective'])
        r.pop('history',None)
    out={'task':'Байесовская оценка солнечного гравитационного параметра по сумме логарифмических правдоподобий','seed':SEED,'n_observations':N,'mu_true_SI':MU_TRUE,'radii_m_range':[float(radii.min()),float(radii.max())],'sigma_definition':'0.005*a_true (m/s^2)','accumulator':'float32 for TNF32/takum32/binary32; float64 only for reference','search':'золотое сечение по log(mu), 72 итерации','results':results}
    path='/home/user/workspace/wave_audit/tnf_downstream_bayesian_si_2026-08-13.json'
    json.dump(out,open(path,'w'),ensure_ascii=False,indent=2)
    print(json.dumps({k:{kk:v for kk,v in r.items() if kk!='history'} for k,r in results.items()},ensure_ascii=False,indent=2))
    print('saved',path)

if __name__=='__main__': main()
