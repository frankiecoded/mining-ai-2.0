import re
import json
import logging
import time
from typing import Dict, Any, Optional, List, Callable
from enum import Enum

logger = logging.getLogger("ai_os.commands")


class CommandState(Enum):
    IDLE = "idle"
    AWAITING_DOCS = "awaiting_docs"
    AWAITING_REMOVE_CONFIRM = "awaiting_remove_confirm"


class UserSession:
    def __init__(self, phone_number: str):
        self.phone_number = phone_number
        self.state = CommandState.IDLE
        self.selected_dataset_index: Optional[int] = None
        self.pending_remove_index: Optional[int] = None
        self.docs_category: str = "general"
        self.docs_description: str = ""
        self.last_activity: float = time.time()

    def reset(self):
        self.state = CommandState.IDLE
        self.selected_dataset_index = None
        self.pending_remove_index = None
        self.docs_category = "general"
        self.docs_description = ""
        self.last_activity = time.time()


class CommandService:
    """
    Parses slash commands from WhatsApp messages and manages user session states.
    Commands are intercepted before reaching the LLM orchestrator.
    """

    COMMANDS = {
        "/help": "Show all available commands",
        "/docs": "Enter file upload mode - send files to build your private dataset",
        "/list": "List all datasets with numbers",
        "/remove": "Remove a dataset (with confirmation)",
        "/status": "Show system status and stats",
        "/price": "Quick gold and precious metals prices",
        "/search": "Search your datasets",
        "/cancel": "Cancel current operation and return to chat",
        "/grade": "Grade calculator - COG, value, dilution, reconciliation",
        "/blast": "Blast design - hole volume, powder factor, timing, vibration",
        "/cost": "Mining cost - AISC, per-oz, per-tonne, comparison",
        "/geology": "Geology helper - minerals, rocks, exploration guidance",
        "/fleet": "Fleet calculator - loader, trucks, diesel consumption",
        "/carbon": "Carbon footprint - emissions, offsets, efficiency",
        "/water": "Water balance - makeup, recycling, treatment sizing",
        "/geotech": "Geotechnical - RMR, slope stability, pillar design",
        "/reserves": "Resource/reserves - classification, JORC compliance",
    }

    def __init__(self):
        self._sessions: Dict[str, UserSession] = {}
        self._handlers: Dict[str, Callable] = {}

    def get_session(self, phone_number: str) -> UserSession:
        if phone_number not in self._sessions:
            self._sessions[phone_number] = UserSession(phone_number)
        session = self._sessions[phone_number]
        if time.time() - session.last_activity > 1800:
            session.reset()
        session.last_activity = time.time()
        return session

    def register_handler(self, command: str, handler: Callable):
        self._handlers[command] = handler

    def parse_command(self, text: str) -> Optional[Dict[str, Any]]:
        text = text.strip()
        if not text.startswith("/"):
            return None

        parts = text.split(maxsplit=1)
        cmd = parts[0].lower()
        args = parts[1] if len(parts) > 1 else ""

        if cmd in self.COMMANDS:
            return {"command": cmd, "args": args, "help": self.COMMANDS[cmd]}

        return {"command": cmd, "args": args, "help": None, "unknown": True}

    def is_command(self, text: str) -> bool:
        return text.strip().startswith("/")

    def handle(self, phone_number: str, text: str, **kwargs) -> Optional[Dict[str, Any]]:
        session = self.get_session(phone_number)

        if session.state == CommandState.AWAITING_DOCS:
            if text.strip().lower() in ("y", "yes", "done", "finish", "complete"):
                return {"type": "docs_finish", "handler": "docs_finish"}
            elif text.strip().lower() in ("n", "no", "cancel"):
                session.reset()
                return {"type": "response", "text": "File upload cancelled. Returning to normal chat."}
            return {"type": "docs_receive", "handler": "docs_receive"}

        if session.state == CommandState.AWAITING_REMOVE_CONFIRM:
            if text.strip().lower() in ("y", "yes", "confirm"):
                index = session.pending_remove_index
                session.reset()
                return {"type": "remove_confirm", "handler": "remove_confirm", "index": index}
            elif text.strip().lower() in ("n", "no", "cancel"):
                session.reset()
                return {"type": "response", "text": "Removal cancelled. Dataset kept."}
            return {"type": "response", "text": "Please reply **yes** to confirm removal or **no** to cancel."}

        parsed = self.parse_command(text)
        if parsed is None:
            return None

        cmd = parsed["command"]

        if cmd == "/help":
            return {"type": "help", "handler": "help"}
        elif cmd == "/docs":
            category = parsed["args"].strip() if parsed["args"] else "general"
            session.state = CommandState.AWAITING_DOCS
            session.docs_category = category
            return {"type": "docs_start", "handler": "docs_start", "category": category}
        elif cmd == "/list":
            return {"type": "list", "handler": "list_datasets"}
        elif cmd == "/remove":
            return {"type": "remove", "handler": "remove_start", "args": parsed["args"]}
        elif cmd == "/status":
            return {"type": "status", "handler": "status"}
        elif cmd == "/price":
            return {"type": "price", "handler": "price"}
        elif cmd == "/search":
            return {"type": "search", "handler": "search_datasets", "args": parsed["args"]}
        elif cmd == "/cancel":
            session.reset()
            return {"type": "response", "text": "Operation cancelled. Back to normal chat."}
        elif cmd in ("/grade", "/blast", "/cost", "/geology", "/fleet", "/carbon", "/water", "/geotech", "/reserves"):
            return {"type": "mining_calc", "handler": cmd.strip("/"), "args": parsed["args"]}
        else:
            return {"type": "unknown", "text": f"Unknown command: `{cmd}`\n\nType /help to see available commands."}
