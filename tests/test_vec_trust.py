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


def test_baseline_ladder_rejects_poly3_without_gain():
    """招牌断言（v0.2 修正版）：正确族是线性时，多项式没有增益 → 应被拒绝准入.

    v0.1 的旧断言"多项式域内赢、外推崩"依赖合成器写死的多项式优势；
    新机制下真实关系就是线性的，poly3 域内 RMSE 与 linear 几乎相同，
    阶梯正确地拒绝它。这比旧版更诚实——基线阶梯的价值正是挡住无增益的复杂模型。
    正确族/错误族的病因区分由 test_diagnose.py 验证。
    """
    result = audit_all(make_atlas())
    ladder = result["baseline_ladder"]
    poly3 = result["per_model"]["poly3"]

    assert ladder["candidate"] == "model"  # baseline_ladder 内部沿用 model 作最高级标签
    assert ladder["admitted"] is False     # 无增益 → 拒绝准入（诚实结论）
    assert poly3["overall_verdict"] == "MODEL_FAIL_TEACHING"
    assert "教学" in poly3["disclaimer"]   # 教学声明随结果返回
