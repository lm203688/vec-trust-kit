"""赛前体检模块测试：Score Mirror / Rule Guard / 格式预检 / Bio Gate."""
from __future__ import annotations

import numpy as np
import pytest

from vec_trust import score_mirror as sm
from vec_trust import rule_guard as rg
from vec_trust import bio_gate as bg
from vec_trust.format_check import precheck, MAX_FILE_MB


# ---------------- Score Mirror ----------------
def test_score_mirror_scale_and_weights():
    r = sm.mirror_score("T1", pred_delta=np.array([1., 0., 0.]),
                        true_delta=np.array([1., 0., 0.]),
                        pred_cells=np.zeros((10, 3)), true_cells=np.zeros((10, 3)))
    assert set(r.per_metric) == {"de_recovery", "direction", "state_distribution", "gene_covariance"}
    assert abs(sum(sm.T1_WEIGHTS.values()) - 1.0) < 1e-9
    assert sm.FLOOR <= r.official_scale <= sm.CEILING
    assert "非官方" in r.disclaimer


def test_score_mirror_disclaimer_on_partial():
    """只提供部分指标时，必须声明缺失指标被重归一化（偏乐观）。"""
    r = sm.mirror_score("T3", pred_delta=np.array([1., 2.]), true_delta=np.array([1., 2.]))
    assert "重归一化" in r.disclaimer


# ---------------- Rule Guard（12 个边界样例）----------------
@pytest.mark.parametrize("stage,expected", [
    ("E8.5", "OK"), ("E9.0", "OK"), ("E9.5", "WARNING"),   # 边界
    ("E10.5", "VIOLATION"), ("E11.5", "VIOLATION"), ("E12.5", "VIOLATION"),
    ("E13.5", "WARNING"), ("E13.6", "WARNING"),  # nearness 半径内的保守告警
    ("E14.0", "OK"), ("E6.75", "OK"),
    (9.45, "WARNING"),   # 伪装成数字的接近边界值
    ("WT", "WARNING"),   # 无法解析 → 告警
    ("E9.49", "WARNING"),
])
def test_t1_window_boundaries(stage, expected):
    f = rg.check_t1_window(stage)
    assert f.level == expected, (stage, f.level, f.detail)


def test_rule_guard_disclosure_and_worst():
    rep = rg.guard(stage="E11.5", gene="Ctnnb1", has_3d_coords=True)
    assert rep.worst == "VIOLATION"
    text = rg.render_disclosure(rep)
    assert "External data disclosure" in text and "E11.5" in text


def test_t3_gene_band():
    assert rg.check_t3_genotype("beta-catenin").level == "VIOLATION"
    assert rg.check_t3_genotype("TP53").level == "OK"


# ---------------- 格式预检 ----------------
def test_precheck_missing_file():
    rep = precheck("nonexistent_xyz.h5ad")
    assert not rep.passed and rep.checks[0].status == "FAIL"


def test_precheck_without_anndata_degrades_gracefully(tmp_path):
    """无 anndata 时应降级检查且明确提示，不能崩溃。"""
    f = tmp_path / "tiny.h5ad"
    f.write_bytes(b"fake")
    rep = precheck(str(f), task="T2")
    statuses = {c.name: c.status for c in rep.checks}
    assert statuses.get("anndata_deep_check") in ("SKIP", "FAIL")  # 取决于环境是否装了 anndata
    assert "非官方" in rep.to_dict()["disclaimer"]


# ---------------- Bio Gate ----------------
def test_composition_gate_pos_neg():
    labels = np.array([0]*80 + [1]*20)
    good = bg.composition_gate(labels, {0: 0.8, 1: 0.2}, tol=0.15)
    bad = bg.composition_gate(labels, {0: 0.5, 1: 0.5}, tol=0.15)
    assert good.passed and not bad.passed
    assert good.score > bad.score


def test_marker_gate_pos_neg():
    rng = np.random.default_rng(0)
    X = rng.normal(0, 0.5, (100, 3))
    lab = np.array([0]*50 + [1]*50)
    X[:50, 0] += 2.0    # gene0 在 type0 高表达
    X[50:, 1] += 2.0    # gene1 在 type1 高表达
    good = bg.marker_gate(X, lab, {0: [0], 1: [1]})
    bad = bg.marker_gate(X, lab, {0: [1], 1: [2]})
    assert good.passed and good.score > bad.score


def test_spatial_gate_continuous_vs_random():
    rng = np.random.default_rng(0)
    n = 60
    base = rng.normal(0, 1, 4)
    coords = rng.normal(0, 1, (n, 3))
    smooth = np.tile(base, (n, 1)) + rng.normal(0, 0.05, (n, 4))  # 平滑
    random = rng.normal(0, 1, (n, 4))                              # 随机
    g_smooth = bg.spatial_continuity_gate(smooth, coords)
    g_random = bg.spatial_continuity_gate(random, coords)
    assert g_smooth.score > g_random.score


def test_bio_report_weakest():
    rep = bg.run_all(
        pred_labels=np.array([0]*90 + [1]*10), prior={0: 0.5, 1: 0.5},  # 组成差
        pred_cellcount=100, prior_count=100,                              # 生长好
        early=1.0, late=0.2,                                              # 谱系好
    )
    assert rep.weakest.gate == "G1_composition"
    assert not rep.passed
