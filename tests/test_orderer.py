"""阅读顺序穷举（order）测试。"""

import pytest

from app.orderer import NoViableOrderError, TiedOrderError, order


def test_unsorted_segments_recover_reading_order():
    r = order(["时习之不", "学而?习之", "之不亦乐乎"])
    assert r["order"] == [1, 0, 2]
    assert r["text"] == "学而时习之不亦乐乎"
    assert r["step_scores"] == [4, 4]
    assert r["total_score"] == 8


def test_sources_use_original_input_indices():
    segments = ["时习之不", "学而?习之", "之不亦乐乎"]
    r = order(segments)
    # "时"：原输入第 1 段的 "?"（下标 2）由原输入第 0 段的 "时"（下标 0）补字
    assert r["sources"][2] == [{"segment": 0, "pos": 0}, {"segment": 1, "pos": 2}]
    # "之"：三段共同贡献，段序号均为原输入下标
    assert r["sources"][4] == [
        {"segment": 0, "pos": 2},
        {"segment": 1, "pos": 4},
        {"segment": 2, "pos": 0},
    ]
    # 每个来源标记必须指回原输入段中真实存在的下标
    for ch, srcs in zip(r["text"], r["sources"]):
        assert srcs
        for s in srcs:
            assert 0 <= s["segment"] < len(segments)
            assert 0 <= s["pos"] < len(segments[s["segment"]])


def test_cumulative_score_selects_best_complete_order():
    # 三种完整顺序的累计得分为 10、12、10，唯一最高为 [1, 2, 0]（12 分）；
    # 若只按原段两两相似度贪心，可能先合并 (2, 0) 而只得 10 分
    r = order(["甲乙丙丁", "丙丁甲乙", "丁甲乙丙"])
    assert r["order"] == [1, 2, 0]
    assert r["text"] == "丙丁甲乙丙丁"
    assert r["step_scores"] == [6, 6]
    assert r["total_score"] == 12


def test_tied_best_orders_raise_with_all_orders():
    with pytest.raises(TiedOrderError) as exc:
        order(["甲乙丙丁", "甲乙丙丁"])
    assert exc.value.total_score == 8
    assert [o["order"] for o in exc.value.orders] == [[0, 1], [1, 0]]
    for o in exc.value.orders:
        assert o["text"] == "甲乙丙丁"
        assert o["total_score"] == 8


def test_no_viable_order_raises():
    with pytest.raises(NoViableOrderError):
        order(["孔子曰未知", "未知生焉", "完全无关文本"])


def test_gate_applies_to_every_step():
    # "之不亦乐乎" 提前与 "学而?习之" 相邻的顺序只能凑出 1 对相同字，不可行
    r = order(["之不亦乐乎", "时习之不", "学而?习之"])
    assert r["order"] == [2, 1, 0]


def test_no_fewer_than_two_segments():
    with pytest.raises(ValueError):
        order(["学而时习之"])
