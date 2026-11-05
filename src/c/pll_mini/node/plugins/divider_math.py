from __future__ import annotations

DTO_MAX_RATIO = 1 << 25


def div_ratio_to_n(ratio: int) -> int:
    if ratio <= 1:
        return 0
    if ratio > 64:
        raise ValueError(f"div ratio {ratio} 超过上限 64")
    return ratio - 1


def dto_ratio_to_step(ratio: int) -> int:
    if ratio <= 0:
        raise ValueError(f"dto ratio {ratio} 须为正")
    max_step = DTO_MAX_RATIO
    step = max_step // ratio
    if step < 1 or step >= max_step:
        raise ValueError(f"dto ratio {ratio} 对应 step {step} 不在 1～2^25-1")
    return step
