import PyImGui
from BehaviorTree.BehaviorTree import BT_ROOT
from BehaviorTree.BT_DebugUI import BTDebugWindow

# Create debugger instance tied to the root tree
debugger = BTDebugWindow(BT_ROOT)

def main():
    # Draw BT debug window
    if PyImGui.begin("BT Tester"):
        debugger.tick()   # tick tree if auto-tick enabled
        debugger.draw()   # draw the BT Debug UI
    PyImGui.end()

if __name__ == "__main__":
    main()
