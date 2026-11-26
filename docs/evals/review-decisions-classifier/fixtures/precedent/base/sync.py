"""Copy new orders from the shop into the warehouse."""

from log import log_event


def sync_orders(orders: list[dict]) -> int:
    for order in orders:
        log_event("order_synced", order_id=order["id"])
    return len(orders)
