"""
PRO-VERSED 24/7 AI Innovation Assistant Engine.
Provides domain-specific intelligence for student creators, mentors, and industry sponsors.
Covers originality recommendations, BOM estimations, grant funding strategies, and platform guidance.
"""

import re
from datetime import datetime
from typing import Dict, Any, List, Optional

class AIChatEngine:
    """Intelligent Innovation Assistant for Bharat Student Innovators."""

    def __init__(self):
        self.knowledge_base = {
            "funding": (
                "💰 **Industry Grants & Commercial Funding on PRO-VERSED:**\n\n"
                "1. **Explore Grants Portal**: Go to the **'Grants & Funding'** tab to see active industry proposals.\n"
                "2. **4 Funding Modalities**:\n"
                "   • *Research & Development Grants* (Direct prototyping funds)\n"
                "   • *Commercial Exclusive/Non-Exclusive Licenses* (IP royalty transfer)\n"
                "   • *Pre-Placement Hiring Packages* (Company pre-recruitment sponsorship)\n"
                "   • *Seed Equity & Prototype Accelerator Funds*\n"
                "3. **Negotiation**: As a student lead or mentor, you can **Accept**, **Decline**, or propose a **Counter-Offer** with 1 click!"
            ),
            "originality": (
                "🛡️ **Smart Originality & Similarity Scanner:**\n\n"
                "• **How it Works**: Pro-Versed uses a sublinear TF-IDF + N-Gram Jaccard matching algorithm to compare your abstract against the national student repository.\n"
                "• **Classification Thresholds**:\n"
                "   • 🟢 **Passed (≥ 85% Unique)**: High novelty verified. Immediate eligibility for mentor sign-off & patent review.\n"
                "   • 🟡 **Moderate Overlap (70% - 84%)**: Review recommended. Refine methodology section.\n"
                "   • 🔴 **Flagged (< 70% Unique)**: Substantial overlap with existing published work. Citation or differentiation required.\n"
                "• **Tip**: Use the 'Originality Check' tab to pre-scan your text before final project submission!"
            ),
            "escrow": (
                "🛍️ **4-Step Safe Buyer Protection Process:**\n\n"
                "1. 🛒 **Step 1 (Order Placed)**: Buyer purchases prototype/software. Payment is safely held in platform protection.\n"
                "2. 🏫 **Step 2 (College Verified)**: Campus Coordinator / Mentor audits non-infringement and verifies item authenticity.\n"
                "3. 📦 **Step 3 (Delivered & Tested)**: Buyer receives physical shipment or private repo access and tests deliverables.\n"
                "4. ✅ **Step 4 (Payment Released)**: Funds are disbursed directly to the student innovator team."
            ),
            "bom": (
                "⚙️ **Hardware Components List (BOM) Best Practices:**\n\n"
                "• **Structure**: Always include Part Name, Quantity, Unit Cost (₹), and Sourcing Link.\n"
                "• **Categories to Track**:\n"
                "   1. Microcontrollers & Compute (e.g. Raspberry Pi 4, STM32H7, Jetson Orin)\n"
                "   2. Sensors & Telemetry (e.g. IMU, LoRa SX1262, LiDAR, Cameras)\n"
                "   3. Actuators & Power (e.g. BLDC Motors, GaN Inverters, LiPo Batteries)\n"
                "   4. Structural & Enclosure (e.g. 3D Print Carbon-Fiber, Custom PCB)\n"
                "• **Surplus Monetization**: You can list extra components on the Project Store!"
            ),
            "ipfs": (
                "🌐 **Decentralized IPFS Storage:**\n\n"
                "• **Immutable Proof**: Storing project archives and model weights on IPFS generates a cryptographic Content Identifier (CID e.g. `QmXoyp...`).\n"
                "• **Tamper-Proof Timestamps**: Guarantees prior art documentation for patent claims.\n"
                "• **Access**: Click on any project's IPFS badge to inspect the cryptographic hash and download verified artifacts."
            ),
            "meeting": (
                "🎥 **Virtual Meeting & Mentor Review Rooms:**\n\n"
                "• **Instant Collaboration**: Open the **'Meeting Room'** tab to start an instant video conference.\n"
                "• **Use Cases**: Conduct milestone audits with faculty mentors or negotiate grant terms with industry buyers.\n"
                "• **Built-In Features**: Camera/Mic toggles, Screen sharing, participant lobby, and instant room links."
            ),
            "task_board": (
                "📋 **Task Board & Faculty Gatekeeper Workflow:**\n\n"
                "• **4 Columns**: **1. To Do** ➔ **2. In Progress** ➔ **3. Under Review** ➔ **4. Completed**.\n"
                "• **Mentor Sign-Off**: When a task is moved to *Under Review*, Faculty Mentors have exclusive permission to click **'Approve & Verify Milestone'** to move it to *Completed*."
            )
        }

    def generate_response(self, user_message: str, user_role: str = "student", user_name: str = "Innovator") -> Dict[str, Any]:
        """Generates contextual AI assistant responses based on natural language queries."""
        msg_lower = user_message.lower()

        suggested_actions = [
            {"label": "💰 How to get Grants?", "query": "How do industry grants work?"},
            {"label": "🛡️ Check Originality", "query": "Explain originality scoring"},
            {"label": "🛍️ Safe Buyer Protection", "query": "How does 4-step escrow work?"},
            {"label": "🎥 Start Video Call", "query": "How do virtual meeting rooms work?"}
        ]

        if any(w in msg_lower for w in ["grant", "fund", "money", "invest", "bid", "sponsor", "commercial", "license"]):
            reply = self.knowledge_base["funding"]
        elif any(w in msg_lower for w in ["plagiarism", "original", "similarity", "unique", "scan", "copy", "score"]):
            reply = self.knowledge_base["originality"]
        elif any(w in msg_lower for w in ["escrow", "bazaar", "store", "buy", "sell", "purchase", "order", "protection"]):
            reply = self.knowledge_base["escrow"]
        elif any(w in msg_lower for w in ["bom", "hardware", "component", "parts", "cost", "budget", "circuit"]):
            reply = self.knowledge_base["bom"]
        elif any(w in msg_lower for w in ["ipfs", "decentral", "hash", "cid", "storage", "crypto"]):
            reply = self.knowledge_base["ipfs"]
        elif any(w in msg_lower for w in ["video", "meeting", "call", "conference", "room", "webrtc"]):
            reply = self.knowledge_base["meeting"]
        elif any(w in msg_lower for w in ["task", "board", "milestone", "review", "audit", "progress", "kanban"]):
            reply = self.knowledge_base["task_board"]
        elif any(w in msg_lower for w in ["hi", "hello", "hey", "who are you", "help"]):
            reply = (
                f"Hello {user_name}! 👋 I am your **PRO-VERSED 24/7 AI Innovation Assistant**.\n\n"
                f"I can assist you with:\n"
                f"• 💰 **Industry Grants & Commercial Licensing**\n"
                f"• 🛡️ **AI Originality & Plagiarism Pre-Checks**\n"
                f"• 📋 **Task Board Milestones & Mentor Reviews**\n"
                f"• 🛍️ **4-Step Safe Buyer Protection Store**\n"
                f"• 🎥 **Virtual Video Collaboration Rooms**\n"
                f"• 🌐 **Decentralized IPFS Storage for Codebases**\n\n"
                f"What would you like assistance with today?"
            )
        else:
            # Smart contextual response based on keywords
            reply = (
                f"Thank you for asking, {user_name}! Here is guidance regarding your inquiry on **PRO-VERSED**:\n\n"
                f"• **For Project Development**: Ensure your project abstract is scanned in the *Originality Check* tab to maintain &ge; 85% uniqueness.\n"
                f"• **For Team Tasks**: Use the *Task Board* to track milestones and request faculty mentor verification in the *Under Review* stage.\n"
                f"• **For Commercialization**: You can list your prototypes on the *Project Store* or receive corporate sponsorships via the *Grants & Funding* portal.\n\n"
                f"Feel free to ask specific questions about any of these modules!"
            )

        return {
            "reply": reply,
            "suggested_actions": suggested_actions,
            "timestamp": datetime.utcnow().isoformat() + "Z"
        }

ai_chat_engine = AIChatEngine()
