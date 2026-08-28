"""
PRO-VERSED IPFS & Decentralized Storage Engine.
Implements Content-Addressed Storage (CAS) with SHA-256 cryptographic hashing,
CID generation, file pinning, and public gateway retrieval for immutable code & project assets.
"""

import os
import hashlib
import json
import base64
import tempfile
from datetime import datetime
from typing import Dict, Any, List, Optional

# Base storage directory for IPFS node simulation
default_ipfs_dir = os.path.join(tempfile.gettempdir(), "proversed_ipfs") if os.name == 'nt' else "/tmp/proversed_ipfs"
IPFS_STORAGE_DIR = os.environ.get("PROVERSED_IPFS_DIR", default_ipfs_dir)
os.makedirs(IPFS_STORAGE_DIR, exist_ok=True)

# Base58 character alphabet for standard IPFS CID encoding
BASE58_ALPHABET = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"

def _b58encode(b: bytes) -> str:
    """Encodes bytes into a Base58 string."""
    n = int.from_bytes(b, "big")
    chars = []
    while n > 0:
        n, r = divmod(n, 58)
        chars.append(BASE58_ALPHABET[r])
    # Count leading zeros
    pad = 0
    for byte in b:
        if byte == 0:
            pad += 1
        else:
            break
    return (BASE58_ALPHABET[0] * pad) + "".join(reversed(chars))

def generate_cid(content_bytes: bytes) -> str:
    """Generates an IPFS v0-compatible multihash CID (Qm...) using SHA-256."""
    sha = hashlib.sha256(content_bytes).digest()
    # Multihash prefix: 0x12 (sha256), 0x20 (32 bytes length)
    multihash = bytes([0x12, 0x20]) + sha
    return _b58encode(multihash)

class IPFSEngine:
    """Decentralized storage manager for student codebases, research models, and BOM assets."""

    def __init__(self, storage_dir: str = IPFS_STORAGE_DIR):
        self.storage_dir = storage_dir
        os.makedirs(self.storage_dir, exist_ok=True)
        self.index_file = os.path.join(self.storage_dir, "ipfs_registry.json")
        self._init_registry()

    def _init_registry(self):
        if not os.path.exists(self.index_file):
            initial_data = {
                "QmXoypizjW3WknFiJnKLwHCnL72vedxjQkDDP1mXWo6uco": {
                    "cid": "QmXoypizjW3WknFiJnKLwHCnL72vedxjQkDDP1mXWo6uco",
                    "filename": "KrishiDrishti_YOLOv8_EdgeWeights.onnx",
                    "size_bytes": 14250000,
                    "mime_type": "application/octet-stream",
                    "pinned": True,
                    "uploader_name": "Aarav Sharma",
                    "project_title": "KrishiDrishti: Autonomous Agri-Drone with Edge-AI",
                    "created_at": "2026-08-15T10:00:00Z"
                },
                "QmZ4tDuvesekSs4qM5ZBKpXiZGun7S2CYtEZRB3DYXkjGx": {
                    "cid": "QmZ4tDuvesekSs4qM5ZBKpXiZGun7S2CYtEZRB3DYXkjGx",
                    "filename": "NeuroFlex_sEMG_DSP_Firmware.zip",
                    "size_bytes": 8420000,
                    "mime_type": "application/zip",
                    "pinned": True,
                    "uploader_name": "Dr. Sunita Verma",
                    "project_title": "NeuroFlex: Non-Invasive Bionic Prosthetic Arm",
                    "created_at": "2026-08-16T14:30:00Z"
                }
            }
            with open(self.index_file, "w") as f:
                json.dump(initial_data, f, indent=2)

    def _load_registry(self) -> Dict[str, Any]:
        if not os.path.exists(self.index_file):
            self._init_registry()
        try:
            with open(self.index_file, "r") as f:
                return json.load(f)
        except Exception:
            return {}

    def _save_registry(self, data: Dict[str, Any]):
        with open(self.index_file, "w") as f:
            json.dump(data, f, indent=2)

    def upload_file(self, filename: str, content: bytes, mime_type: str = "application/octet-stream",
                    uploader_name: str = "Student Innovator", project_title: str = "Student Project") -> Dict[str, Any]:
        """Stores a file by its cryptographic hash (CID) and registers metadata."""
        cid = generate_cid(content)
        file_path = os.path.join(self.storage_dir, cid)

        with open(file_path, "wb") as f:
            f.write(content)

        registry = self._load_registry()
        meta = {
            "cid": cid,
            "filename": filename,
            "size_bytes": len(content),
            "mime_type": mime_type,
            "pinned": True,
            "uploader_name": uploader_name,
            "project_title": project_title,
            "created_at": datetime.utcnow().isoformat() + "Z"
        }
        registry[cid] = meta
        self._save_registry(registry)
        return meta

    def list_files(self) -> List[Dict[str, Any]]:
        """Returns all pinned files in the decentralized storage network."""
        registry = self._load_registry()
        return list(registry.values())

    def get_file_metadata(self, cid: str) -> Optional[Dict[str, Any]]:
        """Fetches metadata for a given Content Identifier (CID)."""
        registry = self._load_registry()
        return registry.get(cid)

    def get_file_content(self, cid: str) -> Optional[bytes]:
        """Retrieves raw file content by CID."""
        file_path = os.path.join(self.storage_dir, cid)
        if os.path.exists(file_path):
            with open(file_path, "rb") as f:
                return f.read()
        return None

ipfs_engine = IPFSEngine()
