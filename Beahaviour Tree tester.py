from __future__ import annotations

import time
from enum import IntEnum
from typing import List, Optional
import PyImGui

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

test_bt = BehaviorTree()
finished = False
input_data = ""

def draw_bt(node, indent=0):
    if node is None:
        return
    prefix = "    " * indent
    PyImGui.text(f"{prefix}{node.name} [{node.node_type}] - State: {node.last_state} - Duration: {node.last_duration_ms:.2f}ms")
    for child in getattr(node, 'children', []):
        draw_bt(child, indent + 1)

def draw_window():
    global test_bt, finished, input_data
    if PyImGui.begin("Behavior Tree Debugger"):
        if PyImGui.button("Reset Tree"):
            test_bt = BehaviorTree()
            finished = False
        # Tick the tree every frame
        if test_bt is not None and not finished:
            state = test_bt.tick()
            if state != NodeState.RUNNING:
                finished = True
        # Draw the tree
        if test_bt is not None:
            draw_bt(test_bt.root)
    PyImGui.end()

def get_ascii_tree_lines(node, prefix="", is_last=True):
    if node is None:
        return []
    # Node type icons
    type_icons = {
        "Selector": "[S]",
        "Sequence": "[>]",
        "Condition": "[?]",
        "Action": "[A]",
        "SubtreeNode": "[T]",
        "None": "[N]"
    }
    # State icons
    state_icons = {
        "NodeState.SUCCESS": "✔",
        "NodeState.FAILURE": "✖",
        "NodeState.RUNNING": "●",
        "None": "○"
    }
    node_type = getattr(node, 'node_type', 'None')
    type_icon = type_icons.get(node_type, '[N]')
    state_val = str(getattr(node, 'last_state', 'None'))
    state_icon = state_icons.get(state_val, '○')
    duration = getattr(node, 'last_duration_ms', 0.0)
    connector = "└── " if is_last else "├── "
    line = f"{prefix}{connector}{type_icon} {node.name} [{node_type}] {state_icon} ({duration:.2f}ms)"
    lines = [line]
    children = getattr(node, 'children', [])
    for i, child in enumerate(children):
        is_child_last = (i == len(children) - 1)
        new_prefix = prefix + ("    " if is_last else "│   ")
        lines.extend(get_ascii_tree_lines(child, new_prefix, is_child_last))
    return lines

def print_tree_ascii_to_console(node):
    for line in get_ascii_tree_lines(node):
        print(line)

# Example usage:
# print_ascii_tree(root)

def main():
    draw_window()

if __name__ == "__main__":
    print_tree_ascii_to_console(BT_ROOT)
