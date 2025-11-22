from __future__ import annotations
# =============================================================
#   BehaviorTree.py — CLEAN TREE STRUCTURE + TIMING
#   Safe for BT viewer, no GW logic yet.
# =============================================================

# Removed xxhash import (module not available). Using internal hash64() wrapper instead.


import time

from enum import IntEnum
from typing import List, Optional

# =============================================================
#   Safe Hash Wrapper (No external dependencies, no Pylance errors)
# =============================================================
try:
    import xxhash  # type: ignore
    def hash64(data: bytes) -> int:
        return xxhash.xxh64(data).intdigest()
except Exception:
    def hash64(data: bytes) -> int:
        """Fallback xxHash64-like hash using Python's built-in hash()."""
        return hash(data) & 0xFFFFFFFFFFFFFFFF

# =============================================================
#   GLOBAL BT TICK COUNTER
# =============================================================
BT_TICK_ID = 0

# =============================================================
#   Perfect Snapshot Mode — Immutable Per-Tick Snapshots
# =============================================================

class NodeSnapshot:
    """
    Immutable per-tick snapshot for a single executed node.
    Contains no references to live node objects.
    """
    __slots__ = (
        "tick_id",
        "exec_index",
        "path_id",
        "parent_path_id",
        "node_type",
        "name",
        "state",
        "duration_ms",
        "extra",
    )

    def __init__(
        self,
        tick_id: int,
        exec_index: int,
        path_id: int,
        parent_path_id: int,
        node_type: str,
        name: str,
        state: str,
        duration_ms: float,
        extra: dict | None = None,
    ):
        self.tick_id = tick_id
        self.exec_index = exec_index
        self.path_id = path_id
        self.parent_path_id = parent_path_id
        self.node_type = node_type
        self.name = name
        self.state = state
        self.duration_ms = duration_ms
        self.extra = extra or {}

class SnapshotBuilder:
    """
    Collects NodeSnapshot entries each tick and produces
    an immutable structure consumed by the BT debugger.
    """

    __slots__ = ("tick_id", "_records")

    def __init__(self) -> None:
        self.tick_id: int = 0
        self._records: list[NodeSnapshot] = []

    def reset(self, tick_id: int) -> None:
        self.tick_id = tick_id
        self._records.clear()

    def record(self, node, state_str: str, duration_ms: float) -> None:
        parent_path_id = 0
        if hasattr(node, "parent") and getattr(node, "parent") is not None:
            parent_path_id = getattr(node.parent, "path_id", 0)

        snap = NodeSnapshot(
            tick_id=self.tick_id,
            exec_index=node.exec_index,
            path_id=node.path_id,
            parent_path_id=parent_path_id,
            node_type=node.node_type,
            name=node.name,
            state=state_str,
            duration_ms=duration_ms,
        )
        self._records.append(snap)

    def build(self) -> dict:
        ordered = sorted(self._records, key=lambda s: s.exec_index)
        by_path = {s.path_id: s for s in ordered}
        return {
            "tick_id": self.tick_id,
            "nodes": ordered,
            "by_path": by_path,
        }

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
        self.last_tick_id = -1
        self.path_id = 0   # 64-bit xxHash of path string
    @classmethod
    def begin_new_tick(cls):
        global BT_TICK_ID
        BT_TICK_ID += 1
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
        from BehaviorTree.BehaviorTree import BT_TICK_ID
        self.last_tick_id = BT_TICK_ID
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
        DummyCondition("IsLoadingScreen", default_result=False),
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
        self._executed_nodes_last_tick = []
        # Perfect Snapshot Mode storage
        self.last_snapshot = None
        self._snapshot_builder = SnapshotBuilder()

    def _build_snapshot(self) -> dict:
        """
        Build a lightweight snapshot of the current tree for the debugger.
        Node IDs are assigned per snapshot and are not stable across ticks.
        Each node gets a stable path_id (xxHash64) based on its path from ROOT.
        """
        snapshot: dict[int, dict] = {}

        def visit(node: Node, next_id: list[int], path_parts: list[str]) -> int:
            # Build this node's path string
            path_str = "/".join(path_parts + [node.name])

            # NEW (use internal hash64 wrapper)
            path_id = hash64(path_str.encode("utf-8"))
            if getattr(node, "path_id", 0) == 0:
                node.path_id = path_id

            nid = next_id[0]
            next_id[0] += 1

            children = getattr(node, "children", [])
            state_enum = getattr(node, "last_state", None)
            state_str = state_enum.name if (state_enum is not None) else None

            snapshot[nid] = {
                "name": getattr(node, "name", f"Node_{nid}"),
                "node_type": getattr(node, "node_type", node.__class__.__name__),
                "state": state_str,
                "last_duration_ms": getattr(node, "last_duration_ms", 0.0),
                "accumulated_ms": getattr(node, "accumulated_ms", 0.0),
                "exec_index": getattr(node, "exec_index", 0),
                "last_tick_id": getattr(node, "last_tick_id", -1),
                "is_active_path": getattr(node, "is_active_path", False),
                "path_id": path_id,
                "children": [],
            }

            # Sort children by exec_index for stable snapshot
            for child in sorted(children, key=lambda c: getattr(c, "exec_index", 0)):
                if child is None:
                    continue
                try:
                    child_id = visit(child, next_id, path_parts + [node.name])
                    snapshot[nid]["children"].append(child_id)
                except AttributeError:
                    continue

            return nid

        if self.root is not None:
            visit(self.root, [1], [])

        return snapshot

    def tick(self) -> NodeState:
        # Begin new tick (clear execution order + active path flags)
        Node.begin_new_tick()

        # Reset snapshot builder with current BT_TICK_ID
        from BehaviorTree.BehaviorTree import BT_TICK_ID
        self._snapshot_builder.reset(BT_TICK_ID)

        if not self.root:
            self._executed_nodes_last_tick = []
            self.last_snapshot = None
            return NodeState.FAILURE

        # Execute root node
        result = self.root.tick()

        # Collect executed nodes
        executed = Node.get_executed_nodes_last_tick()
        self._executed_nodes_last_tick = executed

        # Record snapshots
        for n in executed:
            enum_state = n.last_state
            state_str = enum_state.name if enum_state is not None else "None"
            self._snapshot_builder.record(n, state_str, n.last_duration_ms)

        # Final immutable snapshot
        self.last_snapshot = self._snapshot_builder.build()

        return result

    def GetExecutedNodesLastTick(self):
        return self._executed_nodes_last_tick

    def GetSnapshot(self):
        """
        Return the most recent snapshot for the debugger.
        """
        return self.last_snapshot


__all__ = [
    "BehaviorTree",
    "BT_ROOT",
    "Node",
    "Sequence",
    "Selector",
    "Condition",
    "Action",
    "DummyCondition",
    "DummyAction",
    "NodeState",
]
