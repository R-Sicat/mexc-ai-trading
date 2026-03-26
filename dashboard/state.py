from dataclasses import dataclass, field
from typing import Optional


@dataclass
class BotState:
    is_running: bool = False
    balance: float = 10000.0
    sandbox: bool = True
    last_signal: Optional[dict] = None
    open_position: Optional[dict] = None


bot_state = BotState()
