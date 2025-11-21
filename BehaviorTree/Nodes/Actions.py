from BehaviorTree.BehaviorTree import Action, NodeState


class WaitLoading(Action):
    def __init__(self):
        super().__init__("WaitLoading")

    def tick(self):
        # TODO: will be implemented later
        return NodeState.RUNNING


class WaitMapReady(Action):
    def __init__(self):
        super().__init__("WaitMapReady")

    def tick(self):
        # TODO: will be implemented later
        return NodeState.RUNNING


class MoveIntoCombatPosition(Action):
    def __init__(self):
        super().__init__("MoveIntoCombatPosition")

    def tick(self):
        # TODO: will be implemented in combat phase
        return NodeState.SUCCESS


class UseSkills(Action):
    def __init__(self):
        super().__init__("UseSkills")

    def tick(self):
        # TODO: skill usage logic later
        return NodeState.SUCCESS


class AttackTarget(Action):
    def __init__(self):
        super().__init__("AttackTarget")

    def tick(self):
        # Will be replaced with real attack logic
        return NodeState.SUCCESS


class MoveAndPickup(Action):
    def __init__(self):
        super().__init__("MoveAndPickup")

    def tick(self):
        # TODO: loot logic later
        return NodeState.SUCCESS


class MoveToCommandPoint(Action):
    def __init__(self):
        super().__init__("MoveToCommandPoint")

    def tick(self):
        # TODO: leader movement logic later
        return NodeState.SUCCESS


class GetLeaderPosition(Action):
    def __init__(self):
        super().__init__("GetLeaderPosition")

    def tick(self):
        # TODO: implement later
        return NodeState.SUCCESS


class ComputeFormationOffset(Action):
    def __init__(self):
        super().__init__("ComputeFormationOffset")

    def tick(self):
        # TODO: implement formation math later
        return NodeState.SUCCESS


class MoveToOffset(Action):
    def __init__(self):
        super().__init__("MoveToOffset")

    def tick(self):
        # TODO: formation move logic later
        return NodeState.SUCCESS


class DefendSelf(Action):
    def __init__(self):
        super().__init__("DefendSelf")

    def tick(self):
        # TODO: emergency combat logic later
        return NodeState.SUCCESS


class UseQuickSkill(Action):
    def __init__(self):
        super().__init__("UseQuickSkill")

    def tick(self):
        # TODO: emergency skill logic later
        return NodeState.SUCCESS


class SprintToLeader(Action):
    def __init__(self):
        super().__init__("SprintToLeader")

    def tick(self):
        # TODO: recovery logic later
        return NodeState.SUCCESS
