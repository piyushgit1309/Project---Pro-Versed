"""
PRO-VERSED Video Conference & Virtual Collaboration Service.
Manages meeting rooms for student-mentor milestone audits, project demos, and industry grant negotiations.
"""

import uuid
from datetime import datetime
from typing import Dict, Any, List, Optional

class MeetingService:
    """Virtual Conference and Collaboration Room Manager."""

    def __init__(self):
        self.rooms: Dict[str, Dict[str, Any]] = {
            "ROOM-IITB-KRISHI-01": {
                "id": "ROOM-IITB-KRISHI-01",
                "title": "KrishiDrishti — Milestone 4 Faculty Review Call",
                "project_id": "proj_krishidrishti_01",
                "project_title": "KrishiDrishti: Autonomous Agri-Drone with Edge-AI",
                "host_id": "usr_faculty_01",
                "host_name": "Dr. Sunita Verma",
                "meeting_type": "Mentor Audit",
                "participants_count": 3,
                "is_active": True,
                "jitsi_room_url": "https://meet.jit.si/ProVersed_KrishiDrishti_Review",
                "created_at": "2026-08-18T10:00:00Z"
            },
            "ROOM-GRANT-TATA-02": {
                "id": "ROOM-GRANT-TATA-02",
                "title": "Tata Elxsi — NeuroFlex Bionic Arm Commercialization Pitch",
                "project_id": "proj_neuroflex_02",
                "project_title": "NeuroFlex: Non-Invasive Bionic Prosthetic Arm",
                "host_id": "usr_buyer_01",
                "host_name": "Vikramaditya Singhania",
                "meeting_type": "Industry Pitch",
                "participants_count": 4,
                "is_active": True,
                "jitsi_room_url": "https://meet.jit.si/ProVersed_NeuroFlex_Pitch",
                "created_at": "2026-08-18T11:30:00Z"
            }
        }

    def create_room(self, title: str, host_id: str, host_name: str,
                    project_id: Optional[str] = None, project_title: Optional[str] = None,
                    meeting_type: str = "Collaboration") -> Dict[str, Any]:
        """Creates a new virtual video meeting room."""
        room_code = f"ROOM-PROV-{uuid.uuid4().hex[:6].upper()}"
        clean_title = "".join(c for c in title if c.isalnum() or c == "_")[:24] or "Meeting"
        jitsi_url = f"https://meet.jit.si/ProVersed_{clean_title}_{uuid.uuid4().hex[:4]}"

        room = {
            "id": room_code,
            "title": title,
            "project_id": project_id,
            "project_title": project_title or "General Innovation Discussion",
            "host_id": host_id,
            "host_name": host_name,
            "meeting_type": meeting_type,
            "participants_count": 1,
            "is_active": True,
            "jitsi_room_url": jitsi_url,
            "created_at": datetime.utcnow().isoformat() + "Z"
        }
        self.rooms[room_code] = room
        return room

    def list_rooms(self) -> List[Dict[str, Any]]:
        """Returns all active video conference rooms."""
        return list(self.rooms.values())

    def get_room(self, room_id: str) -> Optional[Dict[str, Any]]:
        """Gets room metadata by room ID."""
        return self.rooms.get(room_id)

meeting_service = MeetingService()
