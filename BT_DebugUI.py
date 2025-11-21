import PyImGui

def draw_bt_debugger_ui(bt_instance):
    PyImGui.set_next_window_size(450, 600, PyImGui.Cond.Once)

    if PyImGui.begin("BT Debugger", True):
        if bt_instance and bt_instance.root:
            draw_node(bt_instance.root)
    PyImGui.end()


def draw_node(node):
    if PyImGui.tree_node(f"{node.name} [{node.state.name}]"):
        # Draw children recursively
        for child in getattr(node, "children", []):
            draw_node(child)
        PyImGui.tree_pop()
