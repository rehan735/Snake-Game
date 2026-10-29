from src.agents.astar_hamilton import AStarHamiltonAgent
from src.agents.base import Agent
from src.mode import Mode


def init_agent(mode: Mode) -> Agent | None:
    if mode == Mode.ASTAR:
        return AStarHamiltonAgent()

    return None
