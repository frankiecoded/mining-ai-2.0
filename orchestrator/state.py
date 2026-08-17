from typing import List, Dict, Any, TypedDict, Annotated, Optional
from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages

class AgentState(TypedDict):
    """
    State representing the context of a execution flow inside the AI OS.
    """
    messages: Annotated[List[BaseMessage], add_messages]
    session_id: str
    phone_number: str
    attachments: List[Dict[str, Any]]  # List of {"storage_uri": str, "mime_type": str, "name": str}
    extracted_data: Dict[str, Any]      # Extracted results from tools/services (e.g., "ocr_text", "search_results")
    output_report: Optional[Dict[str, Any]] # Info about generated PDF or text output
    next_step: str
    interaction_mode: str  # "web_chat" or "voice_note"
