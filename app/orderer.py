"""未排序残页转写的阅读顺序穷举。

接收 2～4 段**未排序**转写，穷举全部排列作为候选阅读顺序；对每种顺序逐段
复用 :func:`app.assembler.assemble_detail` 的合并逻辑——每一步把当前拼接
文本与下一原段做后缀-前缀对齐，沿用续接门槛（最高对齐得分 > 0 且至少有
2 对相同已知字），并**累计各步对齐得分**。任何一步不满足门槛，该顺序即
不可行（不是完整顺序），直接跳过；因此最终比较的是完整顺序的累计得分，
而不是原段两两之间的相似度。

取累计得分最高的完整顺序返回，来源段序号一律换回**原输入下标**：

- 没有任何完整顺序时抛出 :class:`NoViableOrderError`（接口层转为 422）；
- 最高分并列（多个完整顺序累计得分相同）时抛出 :class:`TiedOrderError`，
  携带全部并列顺序（接口层转为 409）。
"""

from __future__ import annotations

from itertools import permutations

from .assembler import MIN_SAME_KNOWN_PAIRS, AssemblyError, assemble_detail


class NoViableOrderError(ValueError):
    """所有排列都无法完整拼接（每种顺序都在某一步不满足续接门槛）。"""

    def __init__(self, tried: int):
        self.tried = tried
        super().__init__(
            f"已穷举 {tried} 种阅读顺序，均无法完整拼接：每步需要最高对齐得分 "
            f"> 0 且至少 {MIN_SAME_KNOWN_PAIRS} 对相同已知字，无完整顺序"
        )


class TiedOrderError(ValueError):
    """最高分并列：多个完整顺序的累计对齐得分相同，无法唯一确定。"""

    def __init__(self, total_score: int, orders: list[dict]):
        self.total_score = total_score
        self.orders = orders
        super().__init__(
            f"存在 {len(orders)} 个累计得分 {total_score} 的并列阅读顺序，"
            f"无法唯一确定"
        )


def _to_original_indices(result: dict, perm: tuple[int, ...]) -> dict:
    """把某一排列下的拼接结果整理为对外结果，来源段序号换回原输入下标。"""
    sources = [
        sorted(
            ({"segment": perm[s["segment"]], "pos": s["pos"]} for s in srcs),
            key=lambda s: (s["segment"], s["pos"]),
        )
        for srcs in result["sources"]
    ]
    return {
        "order": list(perm),
        "text": result["text"],
        "sources": sources,
        "step_scores": result["step_scores"],
        "total_score": result["total_score"],
    }


def order(segments: list[str]) -> dict:
    """穷举 2～4 段未排序转写的阅读顺序，返回累计得分最高的完整顺序。

    返回 ``{"order", "text", "sources", "step_scores", "total_score"}``：
    ``order`` 为原输入下标给出的阅读顺序，``sources`` 的段序号同样为原输入
    下标。失败时抛出 :class:`NoViableOrderError` 或 :class:`TiedOrderError`。
    """
    if len(segments) < 2:
        raise ValueError("至少需要 2 段转写")

    best_score: int | None = None
    best: list[dict] = []
    tried = 0
    for perm in permutations(range(len(segments))):
        tried += 1
        ordered = [segments[i] for i in perm]
        try:
            r = assemble_detail(ordered)
        except AssemblyError:
            continue  # 该顺序在某一步不满足续接门槛，不是完整顺序
        candidate = _to_original_indices(r, perm)
        if best_score is None or candidate["total_score"] > best_score:
            best_score = candidate["total_score"]
            best = [candidate]
        elif candidate["total_score"] == best_score:
            best.append(candidate)

    if not best:
        raise NoViableOrderError(tried)
    if len(best) > 1:
        raise TiedOrderError(best_score, best)
    return best[0]
