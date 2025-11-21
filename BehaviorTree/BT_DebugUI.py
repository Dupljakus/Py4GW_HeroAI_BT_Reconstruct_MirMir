from Py4GWCoreLib import ConsoleLog
# =============================
#  ASCII TREE EXPORTER (Layout E)
# =============================
def _export_ascii_tree(node, prefix="", is_last=True):
    if node is None:
        return ""

    lines = []

    # prefix for connections
    connector = "\\--" if is_last else "+--"

    # gather basic info
    name = getattr(node, "name", "<?>")
    ntype = getattr(node, "node_type", "Node")
    nid = getattr(node, "node_id", 0)
    state = getattr(node, "last_state", None)

    # root node has no connector
    if prefix == "":
        lines.append(f"{ntype}: {name} (ID:{nid}) [{state}]")
    else:
        lines.append(f"{prefix}{connector}{ntype}: {name} (ID:{nid}) [{state}]")

    children = getattr(node, "children", [])
    if not children:
        return "\n".join(lines)

    # prepare new prefix for children
    new_prefix = prefix + ("    " if is_last else "|   ")

    # iterate children
    total = len(children)
    for idx, child in enumerate(children):
        last_child = (idx == total - 1)
        subtree = _export_ascii_tree(child, new_prefix, last_child)
        lines.append(subtree)

    return "\n".join(lines)


import PyImGui
from BehaviorTree import NodeState

from Py4GWCoreLib.ImGui_src.IconsFontAwesome5 import IconsFontAwesome5

# ImGui text color index (ImGuiCol.Text = 0)
TEXT_COLOR_IDX = 0

STATE_COLORS = {
    None:              (0.80, 0.80, 0.80, 1.0),  # not run yet
    NodeState.SUCCESS: (0.20, 0.85, 0.20, 1.0),  # green
    NodeState.FAILURE: (0.90, 0.25, 0.25, 1.0),  # red
    NodeState.RUNNING: (0.25, 0.55, 1.00, 1.0),  # blue for running
}

NODETYPE_COLORS = {
    "Selector":   (0.25, 0.70, 1.00, 1.0),
    "Sequence":   (0.25, 0.70, 1.00, 1.0),
    "Condition":  (0.20, 0.85, 0.20, 1.0),
    "Action":     (1.00, 0.65, 0.00, 1.0),
    "Subtree":    (0.65, 0.45, 1.00, 1.0),
}

DEFAULT_COLOR = (0.80, 0.80, 0.80, 1.0)



# =============================
#  LABEL BUILDER
# =============================
def _node_label(node):
    node_type = getattr(node, "node_type", "Node")
    name = getattr(node, "name", "<?>")
    state = getattr(node, "last_state", None)
    last_ms = getattr(node, "last_duration_ms", 0.0) or 0.0
    accum_ms = getattr(node, "accumulated_ms", 0.0) or 0.0
    exec_index = getattr(node, "exec_index", 0)
    is_active = getattr(node, "is_active_path", False)

    if state == NodeState.SUCCESS:
        state_str = "SUCCESS"
    elif state == NodeState.FAILURE:
        state_str = "FAILURE"
    elif state == NodeState.RUNNING:
        state_str = "RUNNING"
    else:
        state_str = "NONE"

    # Icon mapping
    if node_type == "Selector":
        icon = IconsFontAwesome5.ICON_CODE_BRANCH
    elif node_type == "Sequence":
        icon = IconsFontAwesome5.ICON_STREAM
    elif node_type == "Condition":
        icon = IconsFontAwesome5.ICON_QUESTION_CIRCLE
    elif node_type == "Action":
        icon = IconsFontAwesome5.ICON_BOLT
    elif node_type == "Subtree":
        icon = IconsFontAwesome5.ICON_PROJECT_DIAGRAM
    else:
        icon = ""

    label = (
        f"{icon} [{node_type}] {name} | {state_str} "
        f"[{last_ms:.3f}ms / {accum_ms:.3f}ms]"
    )

    # append execution index
    if exec_index:
        label = f"{label}   #{exec_index}"

    type_color = NODETYPE_COLORS.get(node_type, DEFAULT_COLOR)
    return label, type_color, state_str, last_ms, accum_ms, is_active


# =============================
#  NODE DRAWING
# =============================

def _ui_push_style_color(color):
    PyImGui.push_style_color(TEXT_COLOR_IDX, color)


def _ui_pop_style_color():
    PyImGui.pop_style_color(1)


def draw_node(node):
    if node is None:
        return

    label, type_color, state_str, last_ms, accum_ms, is_active = _node_label(node)
    state = getattr(node, "last_state", None)
    state_color = STATE_COLORS.get(state, DEFAULT_COLOR)
    children = getattr(node, "children", None)
    has_children = bool(children)

    # Determine header text color
    header_color = state_color if is_active else type_color or DEFAULT_COLOR

    # Composite nodes
    if has_children:
        _ui_push_style_color(header_color)
        opened = PyImGui.tree_node(label)
        _ui_pop_style_color()
    else:
        # Leaf nodes: no arrow, just colored label
        if is_active:
            PyImGui.text_colored(label, state_color)
        else:
            PyImGui.text_colored(label, type_color)
        opened = True  # still show details below

    if opened:
        # Details (match the style of the reference screenshot)
        PyImGui.text_colored(f"State: {state_str}", state_color)
        PyImGui.text(f"Last Duration: {last_ms:.3f} ms")
        PyImGui.text(f"Accumulated:  {accum_ms:.3f} ms")
        PyImGui.separator()

        # Visual marker for active nodes
        if is_active:
            PyImGui.text_colored("Active this tick", state_color)
            PyImGui.separator()

        # Draw children inside the same tree node
        if has_children:
            for child in children:
                draw_node(child)
            PyImGui.tree_pop()


# =============================
#  MAIN WINDOW
# =============================

def draw_bt_debugger_ui(root=None):
    if root is None:
        return

    PyImGui.set_next_window_size(450, 650)
    if PyImGui.begin("Behavior Tree Debugger", True):
        if PyImGui.button("Export BT (ASCII) to Console"):
            txt = _export_ascii_tree(root)
            ConsoleLog("BT_Export", txt)
        draw_node(root)
    PyImGui.end()
