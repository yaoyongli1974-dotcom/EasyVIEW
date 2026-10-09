"""分屏布局生成：按窗口数量自动分配大小。

每个窗格用一个 tile 描述：``(row, col, row_span, col_span)``（网格坐标系）。
两种策略：
- 等分（uniform）：所有窗格 1×1，按 ``ceil(sqrt(n))`` 列排布（不足的格子留空）。
- 「1 大 + N 小」（featured）：左上角一个 2×2 大窗（面积是普通窗的 4 倍），
  其余 ``n-1`` 个 1×1 小窗铺满剩余格子。仅当 ``n+3`` 能分解成不太扁的
  ``rows×cols``（长宽比 ≤ 2）时采用，例如 6=1大+5小、5=1大+4小、13=1大+12小。

完美平方数（1/4/9/16/…）一律等分。
"""
from math import isqrt


def uniform_layout(n: int):
    """返回 (rows, cols, tiles)，n 个 1×1 窗格。"""
    n = max(1, int(n))
    cols = isqrt(n)
    if cols * cols < n:
        cols += 1
    rows = (n + cols - 1) // cols
    tiles = [(i // cols, i % cols, 1, 1) for i in range(n)]
    return rows, cols, tiles


def _featured_factor(n: int):
    """求使 rows*cols == n+3 且长宽比 ≤ 2 的最接近正方形的 (rows, cols)。"""
    total = n + 3
    best = None
    for r in range(2, isqrt(total) + 1):
        if total % r == 0:
            c = total // r
            if c >= 2 and max(r, c) <= 2 * min(r, c):
                if best is None or abs(r - c) < abs(best[0] - best[1]):
                    best = (r, c)
    return best


def featured_layout(n: int):
    """「1 大 + N 小」布局；不合适时返回 None。"""
    rc = _featured_factor(n)
    if rc is None:
        return None
    rows, cols = rc
    tiles = [(0, 0, 2, 2)]
    for r in range(rows):
        for c in range(cols):
            if r < 2 and c < 2:
                continue
            tiles.append((r, c, 1, 1))
    return rows, cols, tiles


def auto_layout(n: int, max_channels: int = 64):
    """按窗口数量选择布局，返回 (rows, cols, tiles)，tiles 长度为 n。"""
    n = max(1, min(int(n), int(max_channels)))
    s = isqrt(n)
    if s * s == n:            # 完美平方 -> 等分
        return uniform_layout(n)
    feat = featured_layout(n)  # 否则优先「1 大 + N 小」
    if feat is not None:
        return feat
    return uniform_layout(n)
