"""自测：pytest tests/ -v  （或 python -m pytest tests/ -v）"""
from __future__ import annotations

import numpy as np
import pytest

from vec_trust import (
    conformal_quantile, interval, coverage, w1_proxy, graded_verdict,
    LadderConfig, evaluate_ladder, audit, audit_all,
)
from vec_trust.synthetic import make_atlas, predict_with


def test_conformal_quantile_monotone():
    scores = np.linspace(0, 1, 100)
    q90 = conformal_quantile(scores, 0.1)
    q50 = conformal_quantile(scores, 0.5)
    assert q90 > q50
    assert 0 < q90 <= 1.0


def test_conformal_quantile_rejects_empty():
    with pytest.raises(ValueError):
        conformal_quantile(np.array([np.nan, np.nan]), 0.1)


def test_interval_and_coverage():
    mean = np.zeros(1000)
    std = np.ones(1000)
    lo, hi = interval(mean, std, 1.645)
    y = np.random.default_rng(0).normal(0, 1, 1000)
    assert 0.85 < coverage(lo, hi, y) < 0.95


def test_w1_proxy_detects_shift():
    a = np.random.default_rng(0).normal(0, 1, 500)
    b = a + 3
    assert w1_proxy(a, b) > 2.5
    assert w1_proxy(a, a) < 1e-6


def test_graded_verdict_branches():
    assert graded_verdict(0.92, 0.91, 1.0)[0] == "PASS_PARTIAL"
    assert graded_verdict(0.92, 0.91, 1.0, wet_lab_anchor=True)[0] == "PASS_FULL"
    assert graded_verdict(0.92, 0.72, 1.0)[0] == "PASS_WEAK"
    assert graded_verdict(0.70, 0.70, 1.0)[0] == "MARGINAL"
    assert graded_verdict(0.92, 0.10, 1.0)[0] == "REFUTED"
    # 虚假通过：覆盖虚高但区间宽 20x
    assert graded_verdict(0.95, 0.99, 20.0)[0] == "REFUTED"


def test_baseline_ladder_rejects_no_improvement():
    cfg = LadderConfig(min_improvement=0.05)
    v = evaluate_ladder(0.50, 0.40, 0.30, 0.295, cfg=cfg)
    assert v.admitted is False
    assert v.rejected_by == "linear"


def test_baseline_ladder_admits_clear_win():
    v = evaluate_ladder(0.50, 0.40, 0.30, 0.10)
    assert v.admitted is True
    assert v.candidate == "model"


def test_predict_shapes():
    atlas = make_atlas(n_per_group=10, n_genes=4)
    X, y = atlas["unseen_stage"]
    for name in ("copy_last", "mean", "linear", "model"):
        mu, sd = predict_with(name, *atlas["train"], X)
        assert mu.shape == (len(X), 4)
        assert sd.shape == (len(X), 4)
        assert np.all(sd > 0)


def test_audit_deterministic():
    atlas = make_atlas(n_per_group=40)
    r1 = audit(atlas, "model")
    r2 = audit(atlas, "model")
    assert r1 == r2


def test_core_lesson_domain_win_but_extrap_collapse():
    """本工具的招牌断言：域内赢过基线，外推仍可能全崩。"""
    result = audit_all(make_atlas())
    ladder = result["baseline_ladder"]
    model = result["per_model"]["model"]

    assert ladder["candidate"] == "model"
    assert ladder["admitted"] is True
    assert model["in_domain"]["rmse_rel"] < result["per_model"]["linear"]["in_domain"]["rmse_rel"]
    assert model["overall_verdict"] == "REFUTED"
    assert all(p["verdict"] == "REFUTED" for p in model["protocols"].values())
