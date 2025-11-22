from __future__ import annotations

import PyImGui
from Py4GWCoreLib.py4gwcorelib_src.Color import ColorPalette
from BehaviorTree.BehaviorTree import BehaviorTree, NodeState

# =============================================================
#   UI STATE VARIABLES (SINGLE SOURCE OF TRUTH)
# =============================================================
test_bt = BehaviorTree()
finished = False
input_data = ""
search_query = ""
ui_theme = "Dark"
live_tick = False
node_type_filter = "All"
highlight_query = ""
color_theme = "gw_gold"

THEMES = {
    "Dark": (0.13, 0.14, 0.17, 1),
    "Light": (0.95, 0.95, 0.95, 1),
    "Gold": (0.25, 0.22, 0.13, 1),
}

NODE_TYPE_OPTIONS = ["All", "Selector", "Sequence", "Condition", "Action"]

THEME_NODE_TYPE = {
    "Selector": "gw_blue",
    "Sequence": "gw_green",
    "Condition": "gw_purple",
    "Action": "gw_gold",
    "None": "gray",
}

THEME_NODE_STATE = {
    "RUNNING": "dodger_blue",
    "SUCCESS": "bright_green",
    "FAILURE": "red",
    "None": "gray",
}


# =============================================================
#   HELPERS
# =============================================================

def highlight_text(text: str, query: str):
    if not query:
        return text, (1, 1, 1, 1)
    q = query.lower()
    if q in text.lower():
        return text, (1, 0.7, 0.2, 1)
    return text, (1, 1, 1, 1)


def get_node_stats(node) -> tuple[int, int, int, int]:
    total = running = success = failure = 0

    def _count(n):
        nonlocal total, running, success, failure
        total += 1
        if n.last_state == NodeState.RUNNING:
            running += 1
        elif n.last_state == NodeState.SUCCESS:
            success += 1
        elif n.last_state == NodeState.FAILURE:
            failure += 1
        for child in getattr(n, "children", []):
            _count(child)

    if node is not None:
        _count(node)
    return total, running, success, failure


# =============================================================
#   MAIN WINDOW
# =============================================================

def draw_window():
    global test_bt, finished, input_data, search_query, color_theme
    global live_tick, node_type_filter, highlight_query

    if PyImGui.begin("Behavior Tree Debugger"):
        # -----------------------------------------------------
        # Controls
        # -----------------------------------------------------
        if PyImGui.button("Reset Tree"):
            test_bt = BehaviorTree()
            finished = False
            state = test_bt.tick()
            if state != NodeState.RUNNING:
                finished = True

        # Print Tree button for Py4GW console
        if PyImGui.button("Print Tree"):
            # Pure ASCII tree printer for Py4GW console (no Unicode)
            from Py4GWCoreLib import ConsoleLog, Console

            def get_ascii_tree_lines(node, prefix: str = "", is_last: bool = True):
                if node is None:
                    return []
                type_icons = {
                    "Selector": "[S]",
                    "Sequence": "[>]",
                    "Condition": "[?]",
                    "Action": "[A]",
                    "SubtreeNode": "[T]",
                    "None": "[N]",
                }
                node_type = getattr(node, "node_type", "None")
                type_icon = type_icons.get(node_type, "[N]")
                duration = getattr(node, "last_duration_ms", 0.0)
                connector = "\\-- " if is_last else "+-- "
                line = f"{prefix}{connector}{type_icon} {node.name} [{node_type}] ({duration:.2f}ms)"
                lines = [line]
                children = getattr(node, "children", [])
                for i, child in enumerate(children):
                    is_child_last = (i == len(children) - 1)
                    new_prefix = prefix + ("    " if is_last else "|   ")
                    lines.extend(get_ascii_tree_lines(child, new_prefix, is_child_last))
                return lines

            for line in get_ascii_tree_lines(test_bt.root):
                ConsoleLog("BT_ASCII", line, Console.MessageType.Info, True)

        # -----------------------------------------------------
        # Theme / filters
        # -----------------------------------------------------
        # Color theme picker
        colors = ColorPalette.ListColors()
        try:
            current_index = colors.index(color_theme)
        except ValueError:
            current_index = 0
        new_index = PyImGui.combo("Theme Color", current_index, colors)
        color_theme = colors[new_index]

        PyImGui.separator()

        # Live ticking toggle
        live_tick = PyImGui.checkbox("Live Tick", live_tick)

        # Node type filter dropdown
        node_type_index = NODE_TYPE_OPTIONS.index(node_type_filter)
        node_type_index = PyImGui.combo("Node Type", node_type_index, NODE_TYPE_OPTIONS)
        node_type_filter = NODE_TYPE_OPTIONS[node_type_index]

        PyImGui.separator()

        # Search/filter box
        search_query = PyImGui.input_text("Filter", search_query)
        highlight_query = PyImGui.input_text("Highlight", highlight_query)

        PyImGui.separator()

        # -----------------------------------------------------
        # Stats
        # -----------------------------------------------------
        if PyImGui.tree_node("Stats"):
            total_nodes, running, success, failure = get_node_stats(test_bt.root)
            PyImGui.text(
                f"Nodes: {total_nodes} | RUNNING: {running} | SUCCESS: {success} | FAILURE: {failure}"
            )
            PyImGui.tree_pop()

        # -----------------------------------------------------
        # Snapshot (Perfect Snapshot Mode)
        # -----------------------------------------------------
        snapshot = getattr(test_bt, "last_snapshot", None)
        if PyImGui.tree_node("Snapshot (last tick)"):
            if not snapshot or "nodes" not in snapshot:
                PyImGui.text("No snapshot available yet. Tick the tree at least once.")
            else:
                nodes = snapshot.get("nodes", [])
                # Flat list, ordered by exec_index
                for snap in nodes:
                    state_key = snap.state or "None"
                    node_type = snap.node_type
                    name = snap.name

                    # Text filter
                    if search_query:
                        q = search_query.lower()
                        if q not in name.lower() and q not in node_type.lower():
                            continue

                    # Node-type filter
                    if node_type_filter != "All" and node_type != node_type_filter:
                        continue

                    # Colors by state and type
                    color_name_state = THEME_NODE_STATE.get(state_key, "gray")
                    state_color = ColorPalette.GetColor(color_name_state).to_tuple_normalized()

                    color_name_type = THEME_NODE_TYPE.get(node_type, color_theme)
                    type_color = ColorPalette.GetColor(color_name_type).to_tuple_normalized()

                    color = state_color if state_key != "None" else type_color

                    # Display line
                    text = (
                        f"[{snap.exec_index:03d}] {name} [{node_type}]"
                        f" — {state_key} — {snap.duration_ms:.2f}ms"
                    )
                    text, _ = highlight_text(text, highlight_query)
                    PyImGui.text_colored(text, color)

            PyImGui.tree_pop()

        PyImGui.separator()

        # -----------------------------------------------------
        # Tick tree (live mode)
        # -----------------------------------------------------
        if live_tick and test_bt is not None and not finished:
            state = test_bt.tick()
            if state != NodeState.RUNNING:
                finished = True

        # -----------------------------------------------------
        # Draw tree
        # -----------------------------------------------------
        if test_bt is not None and test_bt.root is not None:
            draw_bt(
                test_bt.root,
                indent=0,
                search_query=search_query,
                force_open=True,
                highlight_query=highlight_query,
                type_filter=node_type_filter,
                color_theme=color_theme,
            )

    PyImGui.end()


# =============================================================
#   LIVE TREE RENDERER
# =============================================================

def draw_bt(
    node,
    indent: int = 0,
    search_query: str = "",
    force_open: bool = False,
    highlight_query: str = "",
    type_filter: str = "All",
    color_theme: str = "gw_gold",
):
    if node is None:
        return

    # Filtering
    if search_query:
        q = search_query.lower()
        if q not in node.name.lower() and q not in node.node_type.lower():
            return

    if type_filter != "All" and node.node_type != type_filter:
        return

    # State → color mapping
    if node.last_state == NodeState.RUNNING:
        node_state_key = "RUNNING"
    elif node.last_state == NodeState.SUCCESS:
        node_state_key = "SUCCESS"
    elif node.last_state == NodeState.FAILURE:
        node_state_key = "FAILURE"
    else:
        node_state_key = "None"

    color_name_state = THEME_NODE_STATE.get(node_state_key, "gray")
    node_state_color = ColorPalette.GetColor(color_name_state).to_tuple_normalized()

    color_name_type = THEME_NODE_TYPE.get(node.node_type, color_theme)
    node_type_color = ColorPalette.GetColor(color_name_type).to_tuple_normalized()

    # Final color rule
    color = node_state_color if node_state_key != "None" else node_type_color
    if node.is_active_path:
        color = ColorPalette.GetColor("yellow").to_tuple_normalized()

    # Prefix for indentation
    prefix = "    " * indent

    icon = (
        "[S] " if node.node_type == "Selector"
        else "[>] " if node.node_type == "Sequence"
        else "[C] " if node.node_type == "Condition"
        else "[A] " if node.node_type == "Action"
        else "[N] "
    )

    # Display line
    info = f"{icon}{node.name} [{node.node_type}] — {node_state_key} — {node.last_duration_ms:.2f}ms"
    if node.is_active_path:
        info += " <ACTIVE>"

    info, _ = highlight_text(info, highlight_query)

    PyImGui.text_colored(prefix + info, color)

    # Tooltip
    if PyImGui.is_item_hovered():
        PyImGui.begin_tooltip()
        PyImGui.text(f"Node: {node.name}")
        PyImGui.text(f"Type: {node.node_type}")
        PyImGui.text(f"State: {node_state_key}")
        PyImGui.text(f"Duration: {node.last_duration_ms:.2f} ms")
        PyImGui.text(f"Accumulated: {node.accumulated_ms:.2f} ms")
        PyImGui.text(f"Exec Index: {node.exec_index}")
        PyImGui.text(f"Active Path: {node.is_active_path}")
        PyImGui.end_tooltip()

    # Render children
    for child in getattr(node, "children", []):
        if child is not None:
            draw_bt(
                child,
                indent + 1,
                search_query,
                force_open,
                highlight_query,
                type_filter,
                color_theme,
            )


# =============================================================
#   WIDGET ENTRYPOINTS
# =============================================================

def main():
    draw_window()


def configure():
    # No special config yet
    pass
