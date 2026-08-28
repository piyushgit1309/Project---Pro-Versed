"""
Database Management Layer for Pro-Versed.
Handles SQLite connection pooling, table schemas, JSON serialization, and seed data initialization.
"""

import sqlite3
import json
import os
import uuid
import tempfile
from datetime import datetime
from typing import List, Dict, Any, Optional

# Supports PROVERSED_DB_PATH or defaults to system temp dir for high-reliability cross-platform execution
default_db_path = os.path.join(tempfile.gettempdir(), "proversed.db") if os.name == 'nt' else "/tmp/proversed.db"
DB_FILE = os.environ.get("PROVERSED_DB_PATH", default_db_path)
db_dir = os.path.dirname(os.path.abspath(DB_FILE))
if db_dir and not os.path.exists(db_dir):
    try:
        os.makedirs(db_dir, exist_ok=True)
    except Exception:
        pass

def get_db_connection() -> sqlite3.Connection:
    """Returns a thread-safe sqlite3 connection with Row factory."""
    conn = sqlite3.connect(DB_FILE, timeout=30.0, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON;")
    return conn

from auth import hash_password

def init_db():
    """Initializes all database tables, performs auto-migrations, and seeds initial state if empty."""
    conn = get_db_connection()
    cursor = conn.cursor()

    # Users Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        email TEXT UNIQUE NOT NULL,
        role TEXT NOT NULL,
        college TEXT,
        department TEXT,
        company TEXT,
        avatar_url TEXT,
        is_verified_academic INTEGER DEFAULT 0,
        is_verified_industry INTEGER DEFAULT 0,
        bio TEXT,
        password_hash TEXT,
        password_salt TEXT,
        reset_password_token TEXT,
        reset_password_expires TEXT,
        is_active INTEGER DEFAULT 1,
        created_at TEXT NOT NULL
    );
    """)

    # Auto-migration for existing databases
    cursor.execute("PRAGMA table_info(users);")
    existing_user_cols = [row["name"] for row in cursor.fetchall()]
    if "password_hash" not in existing_user_cols:
        cursor.execute("ALTER TABLE users ADD COLUMN password_hash TEXT;")
    if "password_salt" not in existing_user_cols:
        cursor.execute("ALTER TABLE users ADD COLUMN password_salt TEXT;")
    if "reset_password_token" not in existing_user_cols:
        cursor.execute("ALTER TABLE users ADD COLUMN reset_password_token TEXT;")
    if "reset_password_expires" not in existing_user_cols:
        cursor.execute("ALTER TABLE users ADD COLUMN reset_password_expires TEXT;")
    if "is_active" not in existing_user_cols:
        cursor.execute("ALTER TABLE users ADD COLUMN is_active INTEGER DEFAULT 1;")

    # Sessions Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS sessions (
        session_id TEXT PRIMARY KEY,
        user_id TEXT NOT NULL,
        created_at TEXT NOT NULL,
        expires_at TEXT NOT NULL,
        last_activity TEXT NOT NULL,
        ip_address TEXT,
        user_agent TEXT,
        is_active INTEGER DEFAULT 1,
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
    );
    """)

    # Login Rate Limiting Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS login_attempts (
        id TEXT PRIMARY KEY,
        ip_address TEXT NOT NULL,
        email TEXT NOT NULL,
        timestamp TEXT NOT NULL,
        is_success INTEGER NOT NULL
    );
    """)

    # Password Reset Rate Limiting Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS password_reset_attempts (
        id TEXT PRIMARY KEY,
        ip_address TEXT NOT NULL,
        email TEXT NOT NULL,
        timestamp TEXT NOT NULL
    );
    """)

    # OTP Verifications Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS otp_verifications (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        email TEXT NOT NULL,
        otp_hash TEXT NOT NULL,
        expires_at TEXT NOT NULL,
        attempts INTEGER DEFAULT 0,
        created_at TEXT NOT NULL
    );
    """)

    # OTP Rate Limiting Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS otp_requests (
        id TEXT PRIMARY KEY,
        ip_address TEXT NOT NULL,
        email TEXT NOT NULL,
        timestamp TEXT NOT NULL
    );
    """)

    # Account Lockout & Security Tracking Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS account_security (
        email TEXT PRIMARY KEY,
        consecutive_failed_attempts INTEGER DEFAULT 0,
        locked_until TEXT,
        last_failed_at TEXT,
        lockout_count INTEGER DEFAULT 0
    );
    """)

    # Projects Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS projects (
        id TEXT PRIMARY KEY,
        title TEXT NOT NULL,
        abstract TEXT NOT NULL,
        description TEXT,
        domain TEXT NOT NULL,
        category TEXT NOT NULL,
        tech_stack TEXT NOT NULL, -- JSON list
        repo_url TEXT,
        demo_url TEXT,
        bom TEXT NOT NULL, -- JSON list of components
        lifecycle_status TEXT NOT NULL, -- Ideation, In Development, Prototype Ready, Completed, Research Published
        originality_score REAL DEFAULT 100.0,
        similarity_index REAL DEFAULT 0.0,
        plagiarism_status TEXT DEFAULT 'PASSED',
        highest_match_project_id TEXT,
        highest_match_title TEXT,
        top_overlapping_keywords TEXT, -- JSON list
        college_name TEXT NOT NULL,
        department TEXT,
        team_lead_id TEXT NOT NULL,
        team_lead_name TEXT NOT NULL,
        faculty_mentor_id TEXT,
        faculty_mentor_name TEXT,
        team_members TEXT, -- JSON list
        patent_status TEXT DEFAULT 'None',
        estimated_budget_inr REAL DEFAULT 0.0,
        stars_count INTEGER DEFAULT 0,
        views_count INTEGER DEFAULT 0,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    );
    """)

    # Kanban Tasks Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS tasks (
        id TEXT PRIMARY KEY,
        project_id TEXT NOT NULL,
        title TEXT NOT NULL,
        description TEXT,
        column TEXT NOT NULL, -- backlog, in_progress, faculty_audit, completed
        priority TEXT NOT NULL, -- Low, Medium, High, Critical
        assignee_name TEXT,
        due_date TEXT,
        faculty_feedback TEXT,
        created_at TEXT NOT NULL,
        FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
    );
    """)

    # Marketplace Items (Pro-Versed Bazaar)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS marketplace_items (
        id TEXT PRIMARY KEY,
        title TEXT NOT NULL,
        description TEXT NOT NULL,
        seller_id TEXT NOT NULL,
        seller_name TEXT NOT NULL,
        seller_college TEXT,
        seller_role TEXT,
        category TEXT NOT NULL, -- Software IP, Hardware Prototype, Hardware Component
        price_inr REAL NOT NULL,
        stock_quantity INTEGER NOT NULL DEFAULT 1,
        technical_specs TEXT, -- JSON dict
        status TEXT DEFAULT 'Available', -- Available, In Escrow, Sold Out
        project_id TEXT,
        image_icon TEXT DEFAULT 'cpu',
        escrow_step INTEGER DEFAULT 1, -- 1: Escrow Held, 2: Mentor Clearance, 3: Shipment/Code Dispatch, 4: Payout Release
        escrow_buyer_id TEXT,
        escrow_buyer_name TEXT,
        escrow_buyer_company TEXT,
        escrow_status_note TEXT,
        created_at TEXT NOT NULL
    );
    """)

    # Industrial Offers (IP Acquisition & Grants)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS industrial_offers (
        id TEXT PRIMARY KEY,
        project_id TEXT NOT NULL,
        project_title TEXT NOT NULL,
        buyer_id TEXT NOT NULL,
        buyer_name TEXT NOT NULL,
        buyer_company TEXT NOT NULL,
        offer_amount_inr REAL NOT NULL,
        proposal_type TEXT NOT NULL, -- Full IP Acquisition, Commercial Exclusive License, Non-Exclusive License, R&D Pilot Grant, Sponsored Student Hiring & IP Transfer
        deliverables_message TEXT,
        status TEXT DEFAULT 'Pending', -- Pending, Accepted, Countered, Rejected
        counter_amount_inr REAL,
        spoc_approval TEXT DEFAULT 'Pending', -- Pending, Approved, Denied
        created_at TEXT NOT NULL
    );
    """)

    # Plagiarism Audit Logs Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS audit_logs (
        id TEXT PRIMARY KEY,
        project_id TEXT,
        project_title TEXT,
        submitted_abstract TEXT,
        similarity_score REAL,
        originality_score REAL,
        status TEXT,
        matched_project_id TEXT,
        matched_project_title TEXT,
        overlapping_keywords TEXT,
        created_at TEXT NOT NULL
    );
    """)

    conn.commit()

    # Ensure all users have valid password hashes
    default_pwhash, default_pwsalt = hash_password("Password123!")
    cursor.execute("""
        UPDATE users 
        SET password_hash = ?, password_salt = ? 
        WHERE password_hash IS NULL OR password_hash = '';
    """, (default_pwhash, default_pwsalt))
    conn.commit()

    # Check if seed data is needed
    cursor.execute("SELECT COUNT(*) FROM users;")
    user_count = cursor.fetchone()[0]
    if user_count == 0:
        seed_initial_data(conn)

    conn.close()

def is_academic_domain(email: str) -> bool:
    """Verifies if email belongs to .ac.in or .edu.in or recognized academic domain."""
    email_lower = email.lower()
    return email_lower.endswith(".ac.in") or email_lower.endswith(".edu.in") or email_lower.endswith(".edu")

def is_industry_domain(email: str) -> bool:
    """Checks if email is a recognized corporate or research enterprise."""
    email_lower = email.lower()
    return any(domain in email_lower for domain in ["tata", "elxsi", "drdo", "isro", "lnt", "mahindra", "infosys", "tcs", "intel", "bosch", "qualcomm"])

def seed_initial_data(conn: sqlite3.Connection):
    """Populates rich national ecosystem seed data."""
    cursor = conn.cursor()

    default_pwhash, default_pwsalt = hash_password("Password123!")

    # Pre-seeded users (Key personas)
    users = [
        {
            "id": "usr_student_1",
            "name": "Aarav Patel",
            "email": "aarav@cse.iitb.ac.in",
            "role": "student",
            "college": "Indian Institute of Technology (IIT) Bombay",
            "department": "Computer Science & Engineering",
            "company": "",
            "avatar_url": "https://api.dicebear.com/7.x/bottts/svg?seed=Aarav",
            "is_verified_academic": 1,
            "is_verified_industry": 0,
            "bio": "Final year B.Tech innovator specializing in Edge-AI, Autonomous Flight, and Embedded Robotics. SIH National Winner.",
            "created_at": "2026-01-10T10:00:00"
        },
        {
            "id": "usr_faculty_1",
            "name": "Dr. Sunita Raman",
            "email": "sunita.raman@iisc.ac.in",
            "role": "faculty",
            "college": "Indian Institute of Science (IISc) Bangalore",
            "department": "Department of Electronic Systems Engineering",
            "company": "",
            "avatar_url": "https://api.dicebear.com/7.x/bottts/svg?seed=Sunita",
            "is_verified_academic": 1,
            "is_verified_industry": 0,
            "bio": "Principal Research Investigator in Cyber-Physical Systems, Bionic Prosthetics, and MEMS Sensor Fabrication.",
            "created_at": "2025-11-05T09:30:00"
        },
        {
            "id": "usr_spoc_1",
            "name": "Prof. R. K. Mukherjee",
            "email": "rk.mukherjee@nitt.edu.in",
            "role": "spoc",
            "college": "National Institute of Technology (NIT) Trichy",
            "department": "Dean of Research & Industrial Consultancy",
            "company": "",
            "avatar_url": "https://api.dicebear.com/7.x/bottts/svg?seed=Mukherjee",
            "is_verified_academic": 1,
            "is_verified_industry": 0,
            "bio": "National Innovation Coordinator & Technology Transfer Officer overseeing 140+ institutional IP patents.",
            "created_at": "2025-08-15T11:00:00"
        },
        {
            "id": "usr_industrialist_1",
            "name": "Vikram Singhania",
            "email": "vikram.s@tataelxsi.com",
            "role": "industrialist",
            "college": "",
            "department": "Autonomous Systems & Strategic IP Acquisition",
            "company": "Tata Elxsi / Tata Motors R&D",
            "avatar_url": "https://api.dicebear.com/7.x/bottts/svg?seed=Vikram",
            "is_verified_academic": 0,
            "is_verified_industry": 1,
            "bio": "Corporate VP seeking ready-to-deploy IoT, ADAS, and Edge-AI prototypes for industrial licensing and deep-tech incubation.",
            "created_at": "2026-02-01T14:15:00"
        },
        {
            "id": "usr_admin_1",
            "name": "Dr. Ananya Sharma",
            "email": "admin@proversed.gov.in",
            "role": "admin",
            "college": "Ministry of Education Innovation Cell (MIC)",
            "department": "National Innovation Portal Administration",
            "company": "",
            "avatar_url": "https://api.dicebear.com/7.x/bottts/svg?seed=Ananya",
            "is_verified_academic": 1,
            "is_verified_industry": 1,
            "bio": "Chief Program Director for National Student Project Registry and Institutional Quality Assurance.",
            "created_at": "2025-06-01T08:00:00"
        }
    ]

    for u in users:
        cursor.execute("""
        INSERT INTO users (id, name, email, role, college, department, company, avatar_url, is_verified_academic, is_verified_industry, bio, password_hash, password_salt, is_active, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?)
        """, (u["id"], u["name"], u["email"], u["role"], u["college"], u["department"], u["company"], u["avatar_url"], u["is_verified_academic"], u["is_verified_industry"], u["bio"], default_pwhash, default_pwsalt, u["created_at"]))

    # Pre-seeded Projects
    projects = [
        {
            "id": "proj_101",
            "title": "KrishiDrishti: Autonomous Agri-Drone with Edge-AI Foliar Disease Diagnosis",
            "abstract": "An autonomous agricultural quadcopter integrated with custom multispectral camera payload and Jetson Orin Nano running quantized YOLOv8 models. Delivers real-time sub-centimeter leaf blight and aphid infestation mapping directly to farmers via LoRa mesh telemetry without requiring active cloud connectivity.",
            "description": "KrishiDrishti bridges precision agriculture with rugged rural hardware. Equipped with an onboard flight computer running ArduPilot, custom carbon-fiber airframe, and an edge inference pipeline capable of detecting 18 varieties of crop diseases at 45 FPS with 94.8% mAP.",
            "domain": "Agritech & Rural Systems",
            "category": "Hybrid",
            "tech_stack": json.dumps(["PyTorch", "TensorRT", "NVIDIA Jetson", "ROS2 Humble", "C++", "ArduPilot", "FastAPI", "React"]),
            "repo_url": "https://github.com/proversed-national/krishidrishti-uav",
            "demo_url": "https://krishidrishti.demo.proversed.in",
            "bom": json.dumps([
                {"item": "NVIDIA Jetson Orin Nano 8GB", "specs": "40 TOPS AI Compute, 1024-core Ampere GPU", "qty": 1, "unit_cost": 42500, "source": "Semiconductor Labs India"},
                {"item": "Custom 650mm Carbon Fiber Quad Frame", "specs": "3K Twill Matte, Vibration Dampened", "qty": 1, "unit_cost": 8500, "source": "AeroMech Bangalore"},
                {"item": "T-Motor MN4014 400KV Brushless Motors", "specs": "Heavy Lift 4S-6S Multi-rotor", "qty": 4, "unit_cost": 3600, "source": "Robu India"},
                {"item": "Multispectral NIR Sensor Module", "specs": "5-Band Spectral (Red, Green, Blue, RedEdge, NIR)", "qty": 1, "unit_cost": 28000, "source": "OptoTech Pune"},
                {"item": "SX1262 LoRa Telemetry Gateway Module", "specs": "868MHz Long Range 10km Mesh", "qty": 2, "unit_cost": 1450, "source": "Electronics Comp"}
            ]),
            "lifecycle_status": "Prototype Ready",
            "originality_score": 96.8,
            "similarity_index": 3.2,
            "plagiarism_status": "PASSED",
            "highest_match_project_id": "proj_103",
            "highest_match_title": "VayuNet LoRa Mesh",
            "top_overlapping_keywords": json.dumps(["lora", "telemetry", "mesh", "sensor"]),
            "college_name": "Indian Institute of Technology (IIT) Bombay",
            "department": "Computer Science & Engineering",
            "team_lead_id": "usr_student_1",
            "team_lead_name": "Aarav Patel",
            "faculty_mentor_id": "usr_faculty_1",
            "faculty_mentor_name": "Dr. Sunita Raman",
            "team_members": json.dumps(["Aarav Patel (Lead)", "Kavya Deshmukh (Embedded)", "Rohan Joshi (Flight Dynamics)", "Sneha Roy (Computer Vision)"]),
            "patent_status": "Provisional Filed",
            "estimated_budget_inr": 115000.0,
            "stars_count": 142,
            "views_count": 1820,
            "created_at": "2026-01-15T10:00:00",
            "updated_at": "2026-02-10T16:00:00"
        },
        {
            "id": "proj_102",
            "title": "NeuroFlex: Non-Invasive Bionic Myoelectric Prosthetic Arm with Haptic Telemetry",
            "abstract": "A 6-DOF high-dexterity upper-limb bionic prosthesis driven by 8-channel surface electromyography (sEMG) arrays and pattern recognition neural networks. Incorporates closed-loop vibrotactile feedback matrices providing amputees with intuitive grip strength sensation.",
            "description": "NeuroFlex offers 3D-printed SLA biomimetic chassis with brushless tendon actuators. The localized microcontroller performs feature extraction using Root Mean Square (RMS) and Wavelet Packet Decomposition, enabling 12 distinct grip gestures with under 42ms actuation latency.",
            "domain": "Biomedical Devices",
            "category": "Hardware",
            "tech_stack": json.dumps(["STM32H7", "Embedded C", "sEMG Signal Processing", "SolidWorks", "TensorFlow Lite Micro", "Bluetooth 5.2"]),
            "repo_url": "https://github.com/proversed-national/neuroflex-bionics",
            "demo_url": "https://neuroflex.iisc.ac.in",
            "bom": json.dumps([
                {"item": "STM32H743ZI Dual-Core MCU Nucleo", "specs": "480MHz Cortex-M7 with FPU & DSP", "qty": 1, "unit_cost": 4800, "source": "STMicroelectronics India"},
                {"item": "8-Channel Dry sEMG Bio-Sensing Array", "specs": "Ag/AgCl active differential leads", "qty": 1, "unit_cost": 12500, "source": "BioSignal Labs"},
                {"item": "Maxon DC Coreless Micro Actuator 12V", "specs": "High torque planetary gearbox 64:1", "qty": 5, "unit_cost": 6200, "source": "Robotics India"},
                {"item": "Linear Resonant Actuator (LRA) Haptics", "specs": "200Hz frequency tuned vibrotactile", "qty": 4, "unit_cost": 850, "source": "Sunrom Electronics"}
            ]),
            "lifecycle_status": "In Development",
            "originality_score": 95.4,
            "similarity_index": 4.6,
            "plagiarism_status": "PASSED",
            "highest_match_project_id": "proj_101",
            "highest_match_title": "KrishiDrishti UAV",
            "top_overlapping_keywords": json.dumps(["microcontroller", "actuation", "signal", "array"]),
            "college_name": "Indian Institute of Science (IISc) Bangalore",
            "department": "Electronic Systems Engineering",
            "team_lead_id": "usr_student_1",
            "team_lead_name": "Tanya Sengupta",
            "faculty_mentor_id": "usr_faculty_1",
            "faculty_mentor_name": "Dr. Sunita Raman",
            "team_members": json.dumps(["Tanya Sengupta (Lead)", "Aditya Verma (Biomedical)", "Karan Malhotra (Mechatronics)"]),
            "patent_status": "None",
            "estimated_budget_inr": 82000.0,
            "stars_count": 98,
            "views_count": 1240,
            "created_at": "2026-01-20T14:30:00",
            "updated_at": "2026-02-12T11:20:00"
        },
        {
            "id": "proj_103",
            "title": "VayuNet: Decentralized Urban Air Quality & PM2.5 Mesh Network with Proof-of-Clean",
            "abstract": "A self-healing urban environmental sensing array utilizing low-power LoRaWAN nodes equipped with laser-scattering particulate sensors (PM1.0, PM2.5, PM10) and electrochemical gas cells (NO2, SO2, CO). Integrates cryptographic sensor attestation on a lightweight hyperledger.",
            "description": "VayuNet provides hyper-local 50-meter microclimate and particulate analytics. Solar-harvesting nodes operate autonomously with 5-year battery lifespans, feeding data into municipal smart-city command centers for dynamic traffic rerouting.",
            "domain": "IoT & Smart Hardware",
            "category": "Hardware",
            "tech_stack": json.dumps(["ESP32-S3", "LoRaWAN", "Rust", "MQTT", "Grafana", "TimescaleDB", "C++", "KiCad"]),
            "repo_url": "https://github.com/proversed-national/vayunet-iot",
            "demo_url": "https://vayunet.nitt.edu.in",
            "bom": json.dumps([
                {"item": "ESP32-S3-WROOM-1 Microcontroller", "specs": "Dual-Core XTensa LX7, 8MB PSRAM", "qty": 10, "unit_cost": 420, "source": "Espressif India"},
                {"item": "Plantower PMS7003 Laser PM Sensor", "specs": "0.3 to 10 micron counting accuracy", "qty": 10, "unit_cost": 1850, "source": "Robu India"},
                {"item": "SX1302 8-Channel LoRaWAN Concentrator", "specs": "SPI Gateway Hat 868MHz", "qty": 1, "unit_cost": 9500, "source": "Seeed India"},
                {"item": "Monocrystalline Solar Panel 5W + MPPT", "specs": "5V 1A LiFePO4 charging circuit", "qty": 10, "unit_cost": 750, "source": "SolarClue"}
            ]),
            "lifecycle_status": "Completed",
            "originality_score": 93.8,
            "similarity_index": 6.2,
            "plagiarism_status": "PASSED",
            "highest_match_project_id": "proj_101",
            "highest_match_title": "KrishiDrishti UAV",
            "top_overlapping_keywords": json.dumps(["lorawan", "nodes", "solar", "mesh"]),
            "college_name": "National Institute of Technology (NIT) Trichy",
            "department": "Instrumentation & Control Engineering",
            "team_lead_id": "usr_student_1",
            "team_lead_name": "Harish Natarajan",
            "faculty_mentor_id": "usr_spoc_1",
            "faculty_mentor_name": "Prof. R. K. Mukherjee",
            "team_members": json.dumps(["Harish Natarajan", "Priya Swaminathan", "R. Karthik"]),
            "patent_status": "Granted",
            "estimated_budget_inr": 48000.0,
            "stars_count": 186,
            "views_count": 2450,
            "created_at": "2025-10-01T09:00:00",
            "updated_at": "2026-01-25T18:00:00"
        },
        {
            "id": "proj_104",
            "title": "QuantumSafe: Lattice-Based Post-Quantum Cryptographic Micro-Vault for FinTech",
            "abstract": "A NIST-standardized Crystals-Kyber (ML-KEM) and Dilithium (ML-DSA) cryptographic hardware security module (HSM) accelerator implemented on FPGA and pure C++ microservices. Protects real-time payment switches and core banking infrastructures from Shor's algorithm attacks.",
            "description": "QuantumSafe implements zero-overhead post-quantum key encapsulation and digital signatures. Tested against high-frequency transaction loads with benchmark latencies below 1.4 milliseconds per signature verification.",
            "domain": "Cyber Security & Blockchain",
            "category": "Software",
            "tech_stack": json.dumps(["Rust", "C++20", "Verilog", "Xilinx Vivado", "FastAPI", "WebAssembly", "Docker"]),
            "repo_url": "https://github.com/proversed-national/quantumsafe-pqc",
            "demo_url": "https://quantumsafe.iiit.ac.in",
            "bom": json.dumps([
                {"item": "Digilent Nexys A7 FPGA Board", "specs": "Artix-7 XC7A100T, 15850 Logic Slices", "qty": 1, "unit_cost": 32000, "source": "Digilent India"},
                {"item": "High-Speed USB 3.0 Telemetry FIFO", "specs": "FTDI FT600Q 3.2 Gbps transceiver", "qty": 1, "unit_cost": 2800, "source": "Mouser India"}
            ]),
            "lifecycle_status": "Research Published",
            "originality_score": 98.4,
            "similarity_index": 1.6,
            "plagiarism_status": "PASSED",
            "highest_match_project_id": "proj_103",
            "highest_match_title": "VayuNet Mesh",
            "top_overlapping_keywords": json.dumps(["cryptographic", "security", "hardware"]),
            "college_name": "International Institute of Information Technology (IIIT) Hyderabad",
            "department": "Center for Security, Theory & Algorithmic Research",
            "team_lead_id": "usr_student_1",
            "team_lead_name": "Nikhil Chawla",
            "faculty_mentor_id": "usr_faculty_1",
            "faculty_mentor_name": "Dr. Sunita Raman",
            "team_members": json.dumps(["Nikhil Chawla", "Divya Reddy", "Prof. P. Shastri"]),
            "patent_status": "Provisional Filed",
            "estimated_budget_inr": 65000.0,
            "stars_count": 215,
            "views_count": 3100,
            "created_at": "2025-09-12T11:00:00",
            "updated_at": "2026-02-05T15:30:00"
        },
        {
            "id": "proj_105",
            "title": "GaN-Volt: High-Frequency Bidirectional Solar MPPT Inverter with Gallium Nitride FETs",
            "abstract": "A 98.6% peak efficiency micro-inverter utilizing GaN power semiconductors operating at 500kHz switching frequency. Achieves a 60% reduction in passive magnetics volume and weight compared to conventional Silicon IGBT topologies, ideal for rooftop solar microgrids and EV fast charging.",
            "description": "GaN-Volt features digitally controlled perturb-and-observe maximum power point tracking with DSP-driven dead-time optimization and active thermal throttling.",
            "domain": "CleanTech & Renewable Energy",
            "category": "Hardware",
            "tech_stack": json.dumps(["TI C2000 DSP", "GaN Systems FETs", "Altium Designer", "MATLAB Simulink", "CAN Bus", "C"]),
            "repo_url": "https://github.com/proversed-national/ganvolt-inverter",
            "demo_url": "https://ganvolt.bits-pilani.ac.in",
            "bom": json.dumps([
                {"item": "GaN Systems GS66508T 650V Power Transistors", "specs": "30A Top-cooled E-HEMT GaN", "qty": 4, "unit_cost": 2200, "source": "Element14 India"},
                {"item": "TI TMS320F280049C Piccolo MCU", "specs": "100MHz C28x with CLA Real-Time Control", "qty": 1, "unit_cost": 1850, "source": "Texas Instruments India"},
                {"item": "High-Frequency Planar Ferrite Transformer", "specs": "Custom 500kHz 2kW EE55 core", "qty": 1, "unit_cost": 3400, "source": "Magnetics Pune"}
            ]),
            "lifecycle_status": "Prototype Ready",
            "originality_score": 94.2,
            "similarity_index": 5.8,
            "plagiarism_status": "PASSED",
            "highest_match_project_id": "proj_103",
            "highest_match_title": "VayuNet Mesh",
            "top_overlapping_keywords": json.dumps(["solar", "mppt", "microcontroller", "efficiency"]),
            "college_name": "Birla Institute of Technology and Science (BITS) Pilani",
            "department": "Electrical & Electronics Engineering",
            "team_lead_id": "usr_student_1",
            "team_lead_name": "Siddharth Menon",
            "faculty_mentor_id": "usr_spoc_1",
            "faculty_mentor_name": "Prof. R. K. Mukherjee",
            "team_members": json.dumps(["Siddharth Menon", "Ananya Hegde"]),
            "patent_status": "None",
            "estimated_budget_inr": 54000.0,
            "stars_count": 112,
            "views_count": 1670,
            "created_at": "2025-11-20T10:00:00",
            "updated_at": "2026-02-01T12:00:00"
        }
    ]

    for p in projects:
        cursor.execute("""
        INSERT INTO projects (id, title, abstract, description, domain, category, tech_stack, repo_url, demo_url, bom, lifecycle_status, originality_score, similarity_index, plagiarism_status, highest_match_project_id, highest_match_title, top_overlapping_keywords, college_name, department, team_lead_id, team_lead_name, faculty_mentor_id, faculty_mentor_name, team_members, patent_status, estimated_budget_inr, stars_count, views_count, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            p["id"], p["title"], p["abstract"], p["description"], p["domain"], p["category"], p["tech_stack"],
            p["repo_url"], p["demo_url"], p["bom"], p["lifecycle_status"], p["originality_score"], p["similarity_index"],
            p["plagiarism_status"], p["highest_match_project_id"], p["highest_match_title"], p["top_overlapping_keywords"],
            p["college_name"], p["department"], p["team_lead_id"], p["team_lead_name"], p["faculty_mentor_id"],
            p["faculty_mentor_name"], p["team_members"], p["patent_status"], p["estimated_budget_inr"],
            p["stars_count"], p["views_count"], p["created_at"], p["updated_at"]
        ))

    # Pre-seeded Tasks for Kanban
    tasks = [
        {
            "id": "tsk_201",
            "project_id": "proj_101",
            "title": "Optimize TensorRT INT8 Quantization Matrix on Jetson Orin",
            "description": "Benchmark frame inference rate from 32 FPS to target 50 FPS without losing foliar lesion mAP above 92%.",
            "column": "in_progress",
            "priority": "High",
            "assignee_name": "Aarav Patel",
            "due_date": "2026-08-25",
            "faculty_feedback": "",
            "created_at": "2026-02-01T10:00:00"
        },
        {
            "id": "tsk_202",
            "project_id": "proj_101",
            "title": "Carbon Fiber Gimbal Vibration Dampening Rig Test",
            "description": "Assemble 3D-printed TPU shock mounts and measure gyro oscillation metrics in 25 km/h wind conditions.",
            "column": "faculty_audit",
            "priority": "Critical",
            "assignee_name": "Rohan Joshi",
            "due_date": "2026-08-20",
            "faculty_feedback": "Dr. Sunita Raman: Vibration data logged within 0.08g. Approved for field validation.",
            "created_at": "2026-01-28T14:00:00"
        },
        {
            "id": "tsk_203",
            "project_id": "proj_101",
            "title": "Integrate Long-Range SX1262 LoRa Telemetry Packets",
            "description": "Establish 9.5km bidirectional flight heartbeat to ground station base terminal.",
            "column": "completed",
            "priority": "Medium",
            "assignee_name": "Kavya Deshmukh",
            "due_date": "2026-02-05",
            "faculty_feedback": "Verified and signed off.",
            "created_at": "2026-01-15T09:00:00"
        },
        {
            "id": "tsk_204",
            "project_id": "proj_101",
            "title": "Autonomous Return-to-Launch (RTL) Geofence Fail-Safe",
            "description": "Program compass interference and low-voltage emergency parachute triggering algorithms.",
            "column": "backlog",
            "priority": "Critical",
            "assignee_name": "Rohan Joshi",
            "due_date": "2026-09-02",
            "faculty_feedback": "",
            "created_at": "2026-02-10T11:00:00"
        },
        {
            "id": "tsk_205",
            "project_id": "proj_102",
            "title": "Design 8-Channel Differential sEMG Front-End Circuit",
            "description": "Layout low-noise instrumentation amplifiers with 50Hz notch filtering on 4-layer PCB.",
            "column": "completed",
            "priority": "High",
            "assignee_name": "Aditya Verma",
            "due_date": "2026-01-30",
            "faculty_feedback": "Passed noise floor test of <1.2uV RMS.",
            "created_at": "2026-01-20T10:00:00"
        },
        {
            "id": "tsk_206",
            "project_id": "proj_102",
            "title": "Implement Wavelet Feature Classifier on STM32H7 DSP",
            "description": "Port trained PyTorch EMG classification weights to CMSIS-NN fixed-point library.",
            "column": "in_progress",
            "priority": "Critical",
            "assignee_name": "Tanya Sengupta",
            "due_date": "2026-08-28",
            "faculty_feedback": "",
            "created_at": "2026-02-02T16:00:00"
        }
    ]

    for t in tasks:
        cursor.execute("""
        INSERT INTO tasks (id, project_id, title, description, column, priority, assignee_name, due_date, faculty_feedback, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (t["id"], t["project_id"], t["title"], t["description"], t["column"], t["priority"], t["assignee_name"], t["due_date"], t["faculty_feedback"], t["created_at"]))

    # Pre-seeded Bazaar Items
    bazaar_items = [
        {
            "id": "baz_301",
            "title": "FoliarVision-YOLOv8 Edge ML Model & Training Pipeline (Commercial License)",
            "description": "Production-ready quantized YOLOv8 model weights trained on 120,000 high-resolution Indian crop foliar disease images across 18 pest classifications. Includes TensorRT conversion scripts, ONNX runtime endpoints, and data augmentation pipeline.",
            "seller_id": "usr_student_1",
            "seller_name": "Aarav Patel",
            "seller_college": "IIT Bombay",
            "seller_role": "Student Innovator",
            "category": "Software IP & Commercial License",
            "price_inr": 45000.0,
            "stock_quantity": 5,
            "technical_specs": json.dumps({
                "Format": "ONNX, TensorRT Engine, PyTorch .pt",
                "Input Resolution": "640x640 RGB",
                "Inference Latency": "18ms on Jetson Orin / 4ms on RTX 4090",
                "mAP @ 0.5:0.95": "94.8%",
                "License Type": "Commercial Dual-Use Transfer"
            }),
            "status": "Available",
            "project_id": "proj_101",
            "image_icon": "code",
            "escrow_step": 1,
            "escrow_buyer_id": "",
            "escrow_buyer_name": "",
            "escrow_buyer_company": "",
            "escrow_status_note": "Awaiting buyer escrow initialization.",
            "created_at": "2026-02-01T12:00:00"
        },
        {
            "id": "baz_302",
            "title": "VayuNet LoRaWAN Smart City Particulate Sensor Cluster (Assembled & Tested)",
            "description": "Turnkey outdoor IP67 solar-powered air monitoring module. Calibrated against reference beta-attenuation monitors with active laser particle counter, temperature, relative humidity, and 868MHz high-gain antenna.",
            "seller_id": "usr_student_1",
            "seller_name": "Harish Natarajan",
            "seller_college": "NIT Trichy",
            "seller_role": "Student Lead",
            "category": "Hardware Prototype (Assembled & Tested)",
            "price_inr": 18500.0,
            "stock_quantity": 3,
            "technical_specs": json.dumps({
                "Enclosure": "IP67 UV-Resistant Polycarbonate",
                "Power System": "3.2V 6000mAh LiFePO4 + 5W Monocrystalline Panel",
                "Sensors": "Plantower PMS7003 + Sensirion SHT40",
                "Range": "Up to 12km Line-of-Sight",
                "Calibration": "Factory Zero-Point Certified"
            }),
            "status": "In Escrow",
            "project_id": "proj_103",
            "image_icon": "bot",
            "escrow_step": 2,
            "escrow_buyer_id": "usr_industrialist_1",
            "escrow_buyer_name": "Vikram Singhania",
            "escrow_buyer_company": "Tata Elxsi / Tata Motors R&D",
            "escrow_status_note": "Stage 2: Escrow locked (₹18,500). Pending Institutional Mentor/SPOC clearance.",
            "created_at": "2026-01-25T14:30:00"
        },
        {
            "id": "baz_303",
            "title": "Surplus Lab BOM: STM32H743ZI Nucleo-144 Dev Boards + IMU Bundles (Qty: 4)",
            "description": "Surplus microcontrollers from completed autonomous vehicle mechatronics research project. Factory sealed with ST-Link V3 debugger and complementary MPU-9250 9-axis motion sensor breakboards.",
            "seller_id": "usr_faculty_1",
            "seller_name": "Dr. Sunita Raman",
            "seller_college": "IISc Bangalore",
            "seller_role": "Faculty Lab Director",
            "category": "Hardware Component & PCB Kit (Surplus BOM)",
            "price_inr": 14200.0,
            "stock_quantity": 4,
            "technical_specs": json.dumps({
                "Microcontroller": "STM32H743ZI 480MHz Cortex-M7",
                "Flash Memory": "2 Megabytes Dual Bank",
                "RAM": "1 Megabyte High-Speed SRAM",
                "Condition": "Brand New, Factory Sealed ESD Packaging"
            }),
            "status": "Available",
            "project_id": "proj_102",
            "image_icon": "cpu",
            "escrow_step": 1,
            "escrow_buyer_id": "",
            "escrow_buyer_name": "",
            "escrow_buyer_company": "",
            "escrow_status_note": "Ready for laboratory dispatch.",
            "created_at": "2026-02-08T10:00:00"
        },
        {
            "id": "baz_304",
            "title": "GaN-Volt 2kW Planar Ferrite High-Frequency Transformer Sub-Assembly",
            "description": "Custom manufactured multi-layer PCB planar transformer designed for 500kHz GaN resonant inverters. Features 99.1% electromagnetic coupling efficiency with integrated Litz wire secondary taps.",
            "seller_id": "usr_student_1",
            "seller_name": "Siddharth Menon",
            "seller_college": "BITS Pilani",
            "seller_role": "Student Innovator",
            "category": "Hardware Component & PCB Kit (Surplus BOM)",
            "price_inr": 7800.0,
            "stock_quantity": 2,
            "technical_specs": json.dumps({
                "Power Rating": "2.2 kW Peak Continuous",
                "Switching Frequency": "350 kHz - 650 kHz",
                "Isolation Voltage": "3.5 kV RMS Hi-Pot Certified",
                "Core Material": "N87 Epcos High-Flux Ferrite"
            }),
            "status": "Available",
            "project_id": "proj_105",
            "image_icon": "zap",
            "escrow_step": 1,
            "escrow_buyer_id": "",
            "escrow_buyer_name": "",
            "escrow_buyer_company": "",
            "escrow_status_note": "Lab verified and ready for shipping.",
            "created_at": "2026-02-04T15:00:00"
        },
        {
            "id": "baz_305",
            "title": "NeuroGait Real-Time Biofeedback PyTorch ML Classifier & Model Weights",
            "description": "Continuous inference neural network for 8-channel surface electromyography decoding with sub-10ms response time. Includes pre-trained weights on 40 patients, data pre-processing scripts, and API server.",
            "seller_id": "usr_student_1",
            "seller_name": "Aditya Verma",
            "seller_college": "IIT Delhi",
            "seller_role": "Student Lead",
            "category": "AI/ML Models",
            "price_inr": 38000.0,
            "stock_quantity": 8,
            "technical_specs": json.dumps({
                "Framework": "PyTorch 2.2 / ONNX Runtime",
                "Input": "8-Channel sEMG Time-Series @ 1kHz",
                "Accuracy": "96.4% Classification Accuracy",
                "License": "Commercial License & Source Code"
            }),
            "status": "Available",
            "project_id": "proj_102",
            "image_icon": "brain",
            "escrow_step": 1,
            "escrow_buyer_id": "",
            "escrow_buyer_name": "",
            "escrow_buyer_company": "",
            "escrow_status_note": "Available for commercial licensing.",
            "created_at": "2026-02-10T09:00:00"
        },
        {
            "id": "baz_306",
            "title": "KrishiDrishti Full-Stack Precision Drone Telemetry & Mission Control System",
            "description": "Enterprise cloud web platform for managing autonomous drone fleets, waypoint telemetry, multispectral NDVI NDVI mapping overlays, and automated PDF spray report generation.",
            "seller_id": "usr_student_1",
            "seller_name": "Aarav Patel",
            "seller_college": "IIT Bombay",
            "seller_role": "Student Innovator",
            "category": "Full-Stack Web/Mobile Systems",
            "price_inr": 52000.0,
            "stock_quantity": 4,
            "technical_specs": json.dumps({
                "Frontend": "React, TailwindCSS, Mapbox GL JS",
                "Backend": "FastAPI, WebSockets, PostgreSQL, Docker",
                "Protocols": "MAVLink 2.0 & MQTT",
                "Deliverables": "Full Git Repo, CI/CD Pipeline & Documentation"
            }),
            "status": "Available",
            "project_id": "proj_101",
            "image_icon": "code-2",
            "escrow_step": 1,
            "escrow_buyer_id": "",
            "escrow_buyer_name": "",
            "escrow_buyer_company": "",
            "escrow_status_note": "Full source code and architecture ready for transfer.",
            "created_at": "2026-02-12T14:00:00"
        },
        {
            "id": "baz_307",
            "title": "NeuroGait 8-Channel Differential sEMG Sensor Array & Analog Front-End",
            "description": "Custom designed multi-channel bio-signal acquisition PCB with active silver-chloride electrode array, 50Hz notch filtering, and SPI ADC output interface for prosthetics researchers.",
            "seller_id": "usr_faculty_1",
            "seller_name": "Dr. Sunita Raman",
            "seller_college": "IISc Bangalore",
            "seller_role": "Faculty Mentor",
            "category": "Sensors & IoT Modules",
            "price_inr": 16500.0,
            "stock_quantity": 6,
            "technical_specs": json.dumps({
                "Channels": "8 Differential Inputs",
                "CMRR": "> 110 dB @ 50 Hz",
                "Sampling Rate": "Up to 4 kSps per channel",
                "Interface": "Isolated SPI & I2C Header"
            }),
            "status": "Available",
            "project_id": "proj_102",
            "image_icon": "cpu",
            "escrow_step": 1,
            "escrow_buyer_id": "",
            "escrow_buyer_name": "",
            "escrow_buyer_company": "",
            "escrow_status_note": "Calibrated and ready for laboratory delivery.",
            "created_at": "2026-02-14T11:30:00"
        }
    ]

    for b in bazaar_items:
        cursor.execute("""
        INSERT INTO marketplace_items (id, title, description, seller_id, seller_name, seller_college, seller_role, category, price_inr, stock_quantity, technical_specs, status, project_id, image_icon, escrow_step, escrow_buyer_id, escrow_buyer_name, escrow_buyer_company, escrow_status_note, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            b["id"], b["title"], b["description"], b["seller_id"], b["seller_name"], b["seller_college"],
            b["seller_role"], b["category"], b["price_inr"], b["stock_quantity"], b["technical_specs"],
            b["status"], b["project_id"], b["image_icon"], b["escrow_step"], b["escrow_buyer_id"],
            b["escrow_buyer_name"], b["escrow_buyer_company"], b["escrow_status_note"], b["created_at"]
        ))

    # Pre-seeded Industrial Bids & Offers
    offers = [
        {
            "id": "off_401",
            "project_id": "proj_101",
            "project_title": "KrishiDrishti: Autonomous Agri-Drone with Edge-AI Foliar Disease Diagnosis",
            "buyer_id": "usr_industrialist_1",
            "buyer_name": "Vikram Singhania",
            "buyer_company": "Tata Elxsi / Tata Motors R&D",
            "offer_amount_inr": 1250000.0, # 12.5 Lakhs
            "proposal_type": "Commercial Exclusive License",
            "deliverables_message": "Tata Elxsi Agriculture Robotics Division proposes to acquire exclusive commercial deployment rights across Maharashtra & Gujarat farm clusters for 3 years, along with funded R&D extension grants and direct pre-placement offers for the core 4 student developers.",
            "status": "Pending",
            "counter_amount_inr": 0.0,
            "spoc_approval": "Pending",
            "created_at": "2026-02-12T14:30:00"
        },
        {
            "id": "off_402",
            "project_id": "proj_104",
            "project_title": "QuantumSafe: Lattice-Based Post-Quantum Cryptographic Micro-Vault",
            "buyer_id": "usr_industrialist_1",
            "buyer_name": "Vikram Singhania",
            "buyer_company": "Tata Elxsi Defense & Aerospace",
            "offer_amount_inr": 2800000.0, # 28 Lakhs
            "proposal_type": "Full IP Acquisition",
            "deliverables_message": "Immediate technology transfer and patent assignment for defense tactical communication encryption systems with royalty pool for student inventors.",
            "status": "Pending",
            "counter_amount_inr": 0.0,
            "spoc_approval": "Pending",
            "created_at": "2026-02-14T09:15:00"
        }
    ]

    for o in offers:
        cursor.execute("""
        INSERT INTO industrial_offers (id, project_id, project_title, buyer_id, buyer_name, buyer_company, offer_amount_inr, proposal_type, deliverables_message, status, counter_amount_inr, spoc_approval, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            o["id"], o["project_id"], o["project_title"], o["buyer_id"], o["buyer_name"], o["buyer_company"],
            o["offer_amount_inr"], o["proposal_type"], o["deliverables_message"], o["status"],
            o["counter_amount_inr"], o["spoc_approval"], o["created_at"]
        ))

    conn.commit()

# Run initialization
init_db()
