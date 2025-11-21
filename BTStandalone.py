
from BehaviorTree.BehaviorTree import BehaviorTree, BT_ROOT
BT_INSTANCE = BehaviorTree()
BT_INSTANCE.root = BT_ROOT

__all__ = ["BT_INSTANCE", "open_bt_debugger", "draw_bt_debugger"]
from BehaviorTree.BT_DebugUI import draw_bt_debugger_ui


def open_bt_debugger() -> None:
    """
    Optional hook if some widget wants to 'open' the debugger.
    For now it is a no-op, because the window is drawn every frame
    via GLOBAL_CACHE.CustomDrawFunctions.
    """
    pass

def draw_bt_debugger() -> None:
    """
    Function that Py4GW_DEMO (or any widget) can register in
    GLOBAL_CACHE.CustomDrawFunctions so that the BT window is drawn
    every frame as an overlay.
    """
    root = getattr(BT_INSTANCE, 'root', None)
    if root is None:
        root = BT_ROOT
    draw_bt_debugger_ui(root)
