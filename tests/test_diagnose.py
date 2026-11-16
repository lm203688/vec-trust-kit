"""R3/R4 验收测试：诊断必须可证伪、能区分病因、带统计区间."""
from __future__ import annotations

import numpy as np
import pytest

from vec_trust import diagnose, paired_ladder_test
from vec_trust.synthetic import make_atlas, predict_with, CORRECT_MODEL, WRONG_MODEL


@pytest.fixture(scope="module")
def atlas():
    return make_atlas(seed=0)


def test_wrong_model_is_model_error(atlas):
    """错误族（三次多项式）外推爆炸 → 必须判 MODEL_ERROR（正控）。"""
    r = diagnose(atlas, WRONG_MODEL, n_boot=6)
    assert r["diagnosis"]["cause"] == "MODEL_ERROR", r["diagnosis"]
    assert r["dimensions"]["model_axis_rmse_ratio"]["unseen_stage"]["mean"] > 1.8


def test_correct_model_static_is_interval_problem(atlas):
    """正确族 + 静态区间：误差稳，但覆盖崩 → INTERVAL_NOT_ADAPTIVE.

    这是相对 v0.1 的关键修正：同一个正确模型，病因不再是笼统的 REFUTED。
    """
    r = diagnose(atlas, CORRECT_MODEL, n_boot=6, scale_mode="static")
    assert r["diagnosis"]["cause"] in ("INTERVAL_NOT_ADAPTIVE", "NONE"), r["diagnosis"]


def test_causes_are_distinguishable_between_models(atlas):
    """正确族与错误族必须落到不同病因（"裁决取决于被测对象"的直接证据）.

    这是 v0.1 恒 REFUTED 缺陷的核心修复验收。
    """
    r_correct = diagnose(atlas, CORRECT_MODEL, n_boot=6)
    r_wrong = diagnose(atlas, WRONG_MODEL, n_boot=6)
    # 正确族：自适应区间能把覆盖救回 → 区间问题
    cov_s = r_correct["dimensions"]["coverage_static"]["unseen_stage"]["mean"]
    cov_a = r_correct["dimensions"]["coverage_adaptive"]["unseen_stage"]["mean"]
    assert cov_a - cov_s > 0.12, (cov_s, cov_a)
    assert r_correct["diagnosis"]["cause"] == "INTERVAL_NOT_ADAPTIVE"
    # 错误族：模型错，与正确族不同
    assert r_wrong["diagnosis"]["cause"] == "MODEL_ERROR"
    assert r_wrong["diagnosis"]["cause"] != r_correct["diagnosis"]["cause"]


def test_confidence_intervals_present(atlas):
    """每个协议都必须有 95% CI，不能只有点估计。"""
    r = diagnose(atlas, CORRECT_MODEL, n_boot=8)
    for dim in ("model_axis_rmse_ratio", "interval_axis_cov_drop"):
        for proto in ("unseen_stage", "unseen_perturbation", "unseen_tissue"):
            ci = r["dimensions"][dim][proto]["ci95"]
            assert len(ci) == 2 and ci[0] <= ci[1]


def test_paired_ladder_test_rejects_noise():
    """配对检验：纯噪声"改进"不能判显著。"""
    rng = np.random.default_rng(0)
    base = rng.normal(0, 1, (200, 5))
    cand = base + rng.normal(0, 0.5, (200, 5))  # 噪声，均值无改进
    r = paired_ladder_test({"linear": base, "model": cand}, seed=1)
    assert r["significant"] is False


def test_paired_ladder_test_detects_real_gain():
    """配对检验：真实且一致的改进应判显著。"""
    rng = np.random.default_rng(0)
    base = rng.normal(1.0, 0.2, (200, 5))
    cand = base - 0.15 + rng.normal(0, 0.02, (200, 5))
    r = paired_ladder_test({"linear": base, "model": cand}, seed=1)
    assert r["significant"] is True
    assert r["mean_error_reduction"] > 0


def test_disclaimer_present(atlas):
    """教学声明必须随结果返回（R1：防止数字被当实证引用）。"""
    r = diagnose(atlas, CORRECT_MODEL, n_boot=4)
    assert "合成" in r["disclaimer"] and "教学" in r["disclaimer"]
