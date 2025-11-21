from BehaviorTree.BehaviorTree import Condition, NodeState

class IsLoadingScreen(Condition):
    def __init__(self):
        super().__init__("IsLoadingScreen")

    def tick(self):
        # TODO: replace with real logic later
        return NodeState.SUCCESS

class MapNotReady(Condition):
    def __init__(self):
        super().__init__("MapNotReady")

    def tick(self):
        # TODO: replace with real logic later
        return NodeState.FAILURE
