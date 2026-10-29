from enum import Enum


class Mode(Enum):
    HUMAN = "This mode lets you play the game yourself."
    ASTAR = "This mode lets an AI play using A* pathfinding + Hamiltonian cycle for maximum score."
