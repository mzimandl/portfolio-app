"""Holdings against the shares they are meant to have."""

from dataclasses import dataclass


@dataclass(frozen=True)
class AllocationRow:
    name: str
    value: float
    share: float | None  # of the whole, now
    target: float  # the share it should have (0.25 means 25 %)
    to_target: float  # what to buy (or, if negative, how much is too many) to be on target now
    buy: float  # this group's part of the new money


def allocation(
    values: dict[str, float], targets: dict[str, float], new_money: float = 0.0
) -> list[AllocationRow]:
    """Compare values per group with target shares, and split new money between the groups.

    The new money only buys: it goes to the groups that would be below their target after
    it is added, in proportion to how far below. Nothing is sold. If no group is below, it
    is split by the targets.
    """
    names = sorted(set(values) | set(targets))
    whole = sum(values.values())
    after = whole + max(new_money, 0.0)
    short = {
        name: max(targets.get(name, 0.0) * after - values.get(name, 0.0), 0.0) for name in names
    }
    total_short = sum(short.values())
    rows = []
    for name in names:
        value, target = values.get(name, 0.0), targets.get(name, 0.0)
        if new_money <= 0:
            buy = 0.0
        elif total_short > 0:
            buy = new_money * short[name] / total_short
        else:
            buy = new_money * target
        rows.append(
            AllocationRow(
                name=name,
                value=value,
                share=value / whole if whole > 0 else None,
                target=target,
                to_target=target * whole - value,
                buy=buy,
            )
        )
    return rows
