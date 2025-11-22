from __future__ import annotations

import time
from enum import IntEnum
from typing import List, Optional
import PyImGui
import random
from Py4GWCoreLib.py4gwcorelib_src.Color import ColorPalette

# =============================================================
#   Node State
# =============================================================

class NodeState(IntEnum):
    SUCCESS = 1
    FAILURE = 2
    RUNNING = 3

# =============================================================
#   Base Node
# =============================================================

class Node:
    # --- Execution path tracking ---
    _executed_nodes_last_tick = []

    def __init__(self, name: str = "Node") -> None:
        self.name: str = name
        self.last_state: Optional[NodeState] = None
        self.last_duration_ms: float = 0.0
        self.accumulated_ms: float = 0.0
        self.node_type: str = self.__class__.__name__
        self.is_active_path = False       # bool
        self.exec_index = 0               # int (order of execution this tick)
    @classmethod
    def begin_new_tick(cls):
        for n in cls._executed_nodes_last_tick:
            n.is_active_path = False
            n.exec_index = 0
        cls._executed_nodes_last_tick.clear()

    @classmethod
    def register_executed(cls, node):
        node.is_active_path = True
        node.exec_index = len(cls._executed_nodes_last_tick) + 1
        cls._executed_nodes_last_tick.append(node)

    @classmethod
    def get_executed_nodes_last_tick(cls):
        return list(cls._executed_nodes_last_tick)

    def tick(self) -> NodeState:
        raise NotImplementedError("tick() must be implemented by subclasses")

    def _finish_tick(self, state: NodeState, start_time: float) -> NodeState:
        """Common timing/profiling logic for all nodes."""
        self.last_state = state
        end = time.perf_counter()
        self.last_duration_ms = (end - start_time) * 1000.0
        self.accumulated_ms += self.last_duration_ms
        type(self).register_executed(self)
        return state

# =============================================================
#   Composite Nodes
# =============================================================

class Sequence(Node):
    def __init__(self, name: str, children: Optional[List[Node]] = None) -> None:
        super().__init__(name)
        self.children: List[Node] = children or []
        self.index: int = 0

    def tick(self) -> NodeState:
        start = time.perf_counter()
        while self.index < len(self.children):
            child = self.children[self.index]
            state = child.tick()

            if state == NodeState.RUNNING:
                return self._finish_tick(NodeState.RUNNING, start)

            if state == NodeState.FAILURE:
                self.index = 0
                return self._finish_tick(NodeState.FAILURE, start)

            # SUCCESS → next child
            self.index += 1

        # Finished sequence
        self.index = 0
        return self._finish_tick(NodeState.SUCCESS, start)

class Selector(Node):
    def __init__(self, name: str, children: Optional[List[Node]] = None) -> None:
        super().__init__(name)
        self.children: List[Node] = children or []

    def tick(self) -> NodeState:
        start = time.perf_counter()
        for child in self.children:
            state = child.tick()

            if state == NodeState.RUNNING:
                return self._finish_tick(NodeState.RUNNING, start)

            if state == NodeState.SUCCESS:
                return self._finish_tick(NodeState.SUCCESS, start)

        return self._finish_tick(NodeState.FAILURE, start)

# =============================================================
#   Leaf Nodes (abstract)
# =============================================================

class Condition(Node):
    def __init__(self, name: str = "Condition") -> None:
        super().__init__(name)

    def condition(self) -> bool:
        """Override in subclasses."""
        raise NotImplementedError

    def tick(self) -> NodeState:
        start = time.perf_counter()
        result = self.condition()
        state = NodeState.SUCCESS if result else NodeState.FAILURE
        return self._finish_tick(state, start)

class Action(Node):
    def __init__(self, name: str = "Action") -> None:
        super().__init__(name)

    def action(self) -> NodeState:
        """Override in subclasses. Must return NodeState."""
        raise NotImplementedError

    def tick(self) -> NodeState:
        start = time.perf_counter()
        state = self.action()
        if not isinstance(state, NodeState):
            # safety fallback
            state = NodeState.FAILURE
        return self._finish_tick(state, start)

# =============================================================
#   Dummy Leaf Nodes (used for now in the tree)
#   They keep BT working without GW logic.
#   node_type is set so the viewer shows [Condition]/[Action].
# =============================================================

class DummyCondition(Condition):
    def __init__(self, name: str, default_result: bool = True) -> None:
        super().__init__(name)
        self.default_result = default_result
        self.node_type = "Condition"

    def condition(self) -> bool:
        return self.default_result

class DummyAction(Action):
    def __init__(self, name: str, default_state: NodeState = NodeState.SUCCESS) -> None:
        super().__init__(name)
        self.default_state = default_state
        self.node_type = "Action"

    def action(self) -> NodeState:
        return self.default_state

# =============================================================
#   BUILD TREE STRUCTURE (EMPTY LOGIC, BUT TIMED)
# =============================================================

def BuildBehaviorTree() -> Node:
    # ----- HandleLoading -----
    handle_loading = Sequence("HandleLoading", [
        DummyCondition("IsLoadingScreen", default_result=True),
        DummyAction("WaitLoading", default_state=NodeState.RUNNING),
    ])

    # ----- HandleMapNotReady -----
    handle_map_not_ready = Sequence("HandleMapNotReady", [
        DummyCondition("MapNotReady", default_result=False),
        DummyAction("WaitMapReady", default_state=NodeState.RUNNING),
    ])

    # ----- Leader Combat -----
    leader_combat = Sequence("LeaderCombat", [
        DummyCondition("DetectEnemiesInRange", default_result=False),
        DummyAction("SelectBestTarget"),
        DummyAction("MoveIntoCombatPosition"),
        DummyAction("UseSkills"),
        DummyAction("AttackTarget"),
    ])

    # ----- Leader Loot -----
    leader_loot = Sequence("LeaderLoot", [
        DummyCondition("DetectLootNearby", default_result=False),
        DummyAction("MoveAndPickup"),
    ])

    # ----- Leader Movement -----
    leader_movement = Sequence("LeaderMovement", [
        DummyCondition("HasMovementCommand", default_result=False),
        DummyAction("MoveToCommandPoint"),
    ])

    leader_branch = Selector("LeaderBranch", [
        leader_combat,
        leader_loot,
        leader_movement,
    ])

    # ----- Follower Emergency Combat -----
    follower_emergency_combat = Sequence("FollowerEmergencyCombat", [
        DummyCondition("EnemyThreatDetected", default_result=False),
        DummyAction("DefendSelf"),
        DummyAction("UseQuickSkill"),
    ])

    # ----- Follower Formation -----
    follower_formation = Sequence("FollowerFormation", [
        DummyAction("GetLeaderPosition"),
        DummyAction("ComputeFormationOffset"),
        DummyAction("MoveToOffset"),
    ])

    # ----- Follower Recovery -----
    follower_recovery = Sequence("FollowerRecovery", [
        DummyCondition("IsTooFarFromLeader", default_result=False),
        DummyAction("SprintToLeader"),
    ])

    follower_branch = Selector("FollowerBranch", [
        follower_emergency_combat,
        follower_formation,
        follower_recovery,
    ])

    # ----- ROOT -----
    root = Selector("ROOT", [
        handle_loading,
        handle_map_not_ready,
        leader_branch,
        follower_branch,
    ])

    return root

# =============================================================
#   GLOBAL ROOT + Wrapper (used by BTStandalone)
# =============================================================

BT_ROOT: Node = BuildBehaviorTree()

class BehaviorTree:
    def __init__(self) -> None:
        self.root: Node = BT_ROOT

    def tick(self) -> NodeState:
        Node.begin_new_tick()  # Start of tick: reset tracking
        if self.root:
            result = self.root.tick()
            self._executed_nodes_last_tick = Node.get_executed_nodes_last_tick()
            return result
        self._executed_nodes_last_tick = []
        return NodeState.FAILURE

    def GetExecutedNodesLastTick(self):
        return self._executed_nodes_last_tick

# =============================================================
#   UI/Debugger
# =============================================================
# --- UI State Variables (initialized for lint and runtime) ---
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
    "Gold": (0.25, 0.22, 0.13, 1)
}
NODE_TYPE_OPTIONS = ["All", "Selector", "Sequence", "Condition", "Action"]

THEME_NODE_TYPE = {
    "Selector": "gw_blue",
    "Sequence": "gw_green",
    "Condition": "gw_purple",
    "Action": "gw_gold",
    "None": "gray"
}
THEME_NODE_STATE = {
    "RUNNING": "dodger_blue",
    "SUCCESS": "bright_green",
    "FAILURE": "red",
    "None": "gray"
}

# Helper for highlight

def highlight_text(text, query):
    if not query:
        return text, (1, 1, 1, 1)
    q = query.lower()
    if q in text.lower():
        return text, (1, 0.7, 0.2, 1)
    return text, (1, 1, 1, 1)

def draw_window():
    global test_bt, finished, input_data, search_query, color_theme, live_tick, node_type_filter, highlight_query
    if PyImGui.begin("Behavior Tree Debugger"):
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
            def get_ascii_tree_lines(node, prefix="", is_last=True):
                if node is None:
                    return []
                type_icons = {
                    "Selector": "[S]",
                    "Sequence": "[>]",
                    "Condition": "[?]",
                    "Action": "[A]",
                    "SubtreeNode": "[T]",
                    "None": "[N]"
                }
                node_type = getattr(node, 'node_type', 'None')
                type_icon = type_icons.get(node_type, '[N]')
                duration = getattr(node, 'last_duration_ms', 0.0)
                connector = "\\-- " if is_last else "+-- "
                line = f"{prefix}{connector}{type_icon} {node.name} [{node_type}] ({duration:.2f}ms)"
                lines = [line]
                children = getattr(node, 'children', [])
                for i, child in enumerate(children):
                    is_child_last = (i == len(children) - 1)
                    new_prefix = prefix + ("    " if is_last else "|   ")
                    lines.extend(get_ascii_tree_lines(child, new_prefix, is_child_last))
                return lines
            for line in get_ascii_tree_lines(test_bt.root):
                ConsoleLog("BT_ASCII", line, Console.MessageType.Info, True)
        # Color theme picker
        color_theme = PyImGui.combo("Theme Color", ColorPalette.ListColors().index(color_theme), ColorPalette.ListColors())
        color_theme = ColorPalette.ListColors()[color_theme]
        PyImGui.separator()
        # Live ticking toggle
        live_tick = PyImGui.checkbox("Live Tick", live_tick)
        # PyImGui.same_line() is only needed for layout, and should not be called here unless placing widgets side by side.
        # Node type filter dropdown
        node_type_index = NODE_TYPE_OPTIONS.index(node_type_filter)
        node_type_index = PyImGui.combo("Node Type", node_type_index, NODE_TYPE_OPTIONS)
        node_type_filter = NODE_TYPE_OPTIONS[node_type_index]
        PyImGui.separator()
        # Search/filter box
        search_query = PyImGui.input_text("Filter", search_query)
        highlight_query = PyImGui.input_text("Highlight", highlight_query)
        PyImGui.separator()
        # Collapsible stats panel
        if PyImGui.tree_node("Stats"):
            total_nodes, running, success, failure = get_node_stats(test_bt.root)
            PyImGui.text(f"Nodes: {total_nodes} | RUNNING: {running} | SUCCESS: {success} | FAILURE: {failure}")
            PyImGui.tree_pop()
        PyImGui.separator()
        # Tick the tree every frame if live_tick is enabled
        if live_tick and test_bt is not None and not finished:
            state = test_bt.tick()
            if state != NodeState.RUNNING:
                finished = True
        # Draw the tree with filter, highlight, and type filter
        if test_bt is not None:
            draw_bt(test_bt.root, 0, search_query, force_open=True, highlight_query=highlight_query, type_filter=node_type_filter, color_theme=color_theme)
    PyImGui.end()

def get_node_stats(node):
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
        for child in getattr(n, 'children', []):
            _count(child)
    _count(node)
    return total, running, success, failure

def draw_bt(node, indent=0, search_query="", force_open=False, highlight_query="", type_filter="All", color_theme="gw_gold"):
    if node is None:
        return
    # Filter logic
    if search_query:
        q = search_query.lower()
        if q not in node.name.lower() and q not in node.node_type.lower():
            return
    if type_filter != "All" and node.node_type != type_filter:
        return
    prefix = "    " * indent
    # Color by state
    node_type_color = ColorPalette.GetColor(THEME_NODE_TYPE.get(node.node_type, color_theme)).to_tuple_normalized()
    node_state_str = str(node.last_state) if node.last_state is not None else "None"
    node_state_color = ColorPalette.GetColor(THEME_NODE_STATE.get(node_state_str, "gray")).to_tuple_normalized()
    color = node_type_color
    if node.last_state == NodeState.RUNNING:
        color = node_state_color
    elif node.last_state == NodeState.SUCCESS:
        color = node_state_color
    elif node.last_state == NodeState.FAILURE:
        color = node_state_color
    if node.is_active_path:
        color = ColorPalette.GetColor("yellow").to_tuple_normalized()
    # ASCII icon by node type
    icon = "[S] " if node.node_type == "Selector" else "[>] " if node.node_type == "Sequence" else "[C] " if node.node_type == "Condition" else "[A] " if node.node_type == "Action" else "[N] "
    info = f"{icon}{node.name} [{node.node_type}] - State: {node.last_state} - Duration: {node.last_duration_ms:.2f}ms"
    if node.is_active_path:
        info += "  <ACTIVE>"
    info, highlight_color = highlight_text(info, highlight_query)
    is_branch = hasattr(node, 'children') and node.children
    # Collapsing magic: root/top-level always expanded, branches are collapsible, leaves are simple
    import math, time
    top_level = (indent == 0)
    if top_level or force_open:
        # Alternating colored text for top-level nodes
        if top_level:
            idx = getattr(node, 'exec_index', 0)
            alt_color1 = (0.4, 0.7, 1, 1)
            alt_color2 = (0.8, 0.9, 0.3, 1)
            node_text_color = alt_color1 if idx % 2 == 0 else alt_color2
        else:
            node_text_color = color
        # Animated highlight for active path
        if node.is_active_path:
            pulse = 0.5 + 0.5 * math.sin(time.time() * 4)
            pulse_color = (1, 1, 0.2 * pulse, 1)
            PyImGui.text_colored(info, pulse_color)
        else:
            PyImGui.text_colored(info, node_text_color)
        # Add divider between top-level nodes
        if top_level:
            PyImGui.separator()
        # Children: branches are collapsible, leaves are simple
        for child in getattr(node, 'children', []):
            is_branch = hasattr(child, 'children') and child.children
            if is_branch:
                if PyImGui.tree_node(f"{child.name} [{child.node_type}]"):
                    # Tooltip for branch
                    if PyImGui.is_item_hovered():
                        PyImGui.begin_tooltip()
                        PyImGui.text(f"Node: {child.name}")
                        PyImGui.text(f"Type: {child.node_type}")
                        PyImGui.text(f"State: {child.last_state}")
                        PyImGui.text(f"Duration (ms): {child.last_duration_ms:.2f}")
                        PyImGui.text(f"Accumulated (ms): {child.accumulated_ms:.2f}")
                        PyImGui.text(f"Exec Index: {child.exec_index}")
                        PyImGui.text(f"Active Path: {child.is_active_path}")
                        PyImGui.end_tooltip()
                    # Recursively draw branch
                    draw_bt(child, indent + 1, search_query, force_open=False, highlight_query=highlight_query, type_filter=type_filter, color_theme=color_theme)
                    PyImGui.tree_pop()
            else:
                # Leaf node
                PyImGui.text_colored("    " * (indent + 1) + f"{child.name} [{child.node_type}] - State: {child.last_state} - Duration: {child.last_duration_ms:.2f}ms", color)
                if PyImGui.is_item_hovered():
                    PyImGui.begin_tooltip()
                    PyImGui.text(f"Node: {child.name}")
                    PyImGui.text(f"Type: {child.node_type}")
                    PyImGui.text(f"State: {child.last_state}")
                    PyImGui.text(f"Duration (ms): {child.last_duration_ms:.2f}")
                    PyImGui.text(f"Accumulated (ms): {child.accumulated_ms:.2f}")
                    PyImGui.text(f"Exec Index: {child.exec_index}")
                    PyImGui.text(f"Active Path: {child.is_active_path}")
                    PyImGui.end_tooltip()
    # If not top-level and not force_open, handle branch/leaves as before
    elif is_branch:
        if PyImGui.tree_node(info):
            if PyImGui.is_item_hovered():
                PyImGui.begin_tooltip()
                PyImGui.text(f"Node: {node.name}")
                PyImGui.text(f"Type: {node.node_type}")
                PyImGui.text(f"State: {node.last_state}")
                PyImGui.text(f"Duration (ms): {node.last_duration_ms:.2f}")
                PyImGui.text(f"Accumulated (ms): {node.accumulated_ms:.2f}")
                PyImGui.text(f"Exec Index: {node.exec_index}")
                PyImGui.text(f"Active Path: {node.is_active_path}")
                PyImGui.end_tooltip()
            for child in node.children:
                draw_bt(child, indent + 1, search_query, force_open, highlight_query=highlight_query, type_filter=type_filter, color_theme=color_theme)
            PyImGui.tree_pop()
    else:
        PyImGui.text_colored(prefix + info, color)
        if PyImGui.is_item_hovered():
            PyImGui.begin_tooltip()
            PyImGui.text(f"Node: {node.name}")
            PyImGui.text(f"Type: {node.node_type}")
            PyImGui.text(f"State: {node.last_state}")
            PyImGui.text(f"Duration (ms): {node.last_duration_ms:.2f}")
            PyImGui.text(f"Accumulated (ms): {node.accumulated_ms:.2f}")
            PyImGui.text(f"Exec Index: {node.exec_index}")
            PyImGui.text(f"Active Path: {node.is_active_path}")
            PyImGui.end_tooltip()

def main():
    draw_window()

def configure():
    pass
