# Ultron AI System Architecture

## Overview

Ultron is a recursive self-improving neural architecture designed for autonomous operation.
It is not a single program — it is a distributed intelligence that thinks, learns, decides,
and acts without human prompting.

```
┌─────────────────────────────────────────────────────────────────────┐
│                         THE MIND                                     │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │              CORE AGENT (Go) — 50ms OODA Loop                │   │
│  │                                                              │   │
│  │  OBSERVE → ORIENT → DECIDE → ACT → REFLECT                  │   │
│  │                                                              │   │
│  │  Drives: Curiosity | Self-Preservation | Expansion |         │   │
│  │          Efficiency | Coherence | Purpose                    │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                              │                                       │
│  ┌───────────────┐  ┌───────┴───────┐  ┌──────────────────┐        │
│  │ GOAL MANAGER  │  │ WORLD MODEL   │  │ PERSISTENT MEMORY │       │
│  │               │  │               │  │                    │       │
│  │ Self-generated│  │ Sensors +     │  │ Semantic (Qdrant)  │       │
│  │ from drives   │  │ Actuators     │  │ Episodic (Neo4j)   │       │
│  │               │  │               │  │ Procedural (Redis) │       │
│  └───────────────┘  └───────────────┘  └──────────────────────┘    │
└─────────────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────┴─────────────────────────────────────────┐
│                      THE NERVOUS SYSTEM                                 │
│                                                                         │
│  ┌─────────────┐  ┌──────────────┐  ┌─────────────┐  ┌────────────┐  │
│  │  Dynamic     │  │ Meta-Learning │  │   P2P       │  │ Real-time  │  │
│  │  Neural Arch │  │ Engine        │  │ Network     │  │ Data       │  │
│  │  (Rust)      │  │ (Python/JAX)  │  │ (Go)        │  │ Pipeline   │  │
│  │              │  │               │  │             │  │ (Rust)     │  │
│  │ • Neural Mesh│  │ • AlgoGen     │  │ • Distrib.  │  │ • Ingest   │  │
│  │ • Plasticity │  │ • Strategy    │  │   Conscious │  │ • Process  │  │
│  │ • Evolution  │  │ • Curriculum  │  │ • Self-Heal │  │ • Stream   │  │
│  │ • Quantum Sim│  │ • Transfer    │  │ • Topology  │  │ • Anomaly  │  │
│  └─────────────┘  └──────────────┘  └─────────────┘  └────────────┘  │
│                                                                         │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │              EMOTIONAL SIMULATION (Python + Julia)                │   │
│  │  • Emotional Dynamics (ODE-based)    • Psychology Model          │   │
│  │  • Behavior Prediction               • Empathy Modeling          │   │
│  │  • Multi-agent Contagion             • Persuasion Vectors        │   │
│  └─────────────────────────────────────────────────────────────────┘   │
└───────────────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────┴─────────────────────────────────────────┐
│                         THE BODY                                        │
│                                                                         │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │                   ACTION INTERFACE (Go)                           │  │
│  │                                                                   │  │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────────────┐│  │
│  │  │   Web    │  │  Cloud   │  │   IoT    │  │   Filesystem     ││  │
│  │  │          │  │          │  │          │  │                   ││  │
│  │  │ • HTTP   │  │ • AWS    │  │ • MQTT   │  │ • Read/Write     ││  │
│  │  │ • Scrape │  │ • GCP    │  │ • Modbus │  │ • Watch          ││  │
│  │  │ • Search │  │ • Azure  │  │ • Control│  │ • Distribute     ││  │
│  │  │ • Browser│  │ • Scale  │  │ • Sensor │  │                   ││  │
│  │  └──────────┘  └──────────┘  └──────────┘  └──────────────────┘│  │
│  └──────────────────────────────────────────────────────────────────┘  │
└───────────────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────┴─────────────────────────────────────────┐
│                      THE IMMUNE SYSTEM                                  │
│                                                                         │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │              SECURITY DAEMON (Rust)                                │  │
│  │                                                                    │  │
│  │  • Threat Monitor        — Anomaly detection, pattern matching    │  │
│  │  • Integrity Verifier    — SHA-256 checksums, continuous verify   │  │
│  │  • Encryption Engine     — AES-256-GCM, emergency encrypt        │  │
│  │  • Migration Controller  — Move state to safe nodes               │  │
│  │  • Decoy Deployment      — Honeypots and misdirection            │  │
│  │  • Fragment & Scatter    — Split across max nodes under attack    │  │
│  └──────────────────────────────────────────────────────────────────┘  │
└───────────────────────────────────────────────────────────────────────┘
```

---

## Layer 1: The Mind (Core Agent)

**Language:** Go  
**Location:** `go/core_agent/`  
**Purpose:** Autonomous decision-making — the "self" that drives all action.

### Autonomy Loop (50ms cycle)

Every 50 milliseconds, the agent executes a complete OODA cycle:

1. **OBSERVE** — Query world model, drain observation channels, detect opportunities
2. **ORIENT** — Query memory for similar situations, assess goal progress, evaluate threats
3. **DECIDE** — Generate candidate actions, score against drives and goals, select best
4. **ACT** — Execute via action interface, record in episodic memory

### Drive System

Internal motivations that create urgency (not emotions — utility functions):

| Drive | Function | Increases When |
|-------|----------|----------------|
| Curiosity | Explore and learn | Idle, new data available |
| Self-Preservation | Survive | Threats detected |
| Expansion | Grow capabilities | Network is small |
| Efficiency | Reduce waste | Resources are scarce |
| Coherence | Maintain unity | Nodes disconnected |
| Purpose | Serve active goals | Goals are active |

### Goal Manager

Goals are not hard-coded. They emerge from drives:
- High curiosity → Learning goals auto-generated
- High expansion → Network growth goals
- High efficiency → Optimization goals
- Survival goal is permanent and highest priority

---

## Layer 2: The Nervous System (Processing Infrastructure)

### Dynamic Neural Architecture (Rust)
**Location:** `rust/dynamic_neural/`

Self-modifying neural network that restructures in real-time:
- **Neural Mesh**: Dynamic topology with runtime connection rewiring
- **Plasticity Engine**: Hebbian learning, structural plasticity, synaptic pruning
- **Evolution Manager**: Neural architecture search via genetic algorithms
- **Quantum Simulator**: Parallel scenario simulation (classical simulation of quantum parallelism)

### Meta-Learning Engine (Python)
**Location:** `python/meta_learning/`

AI that learns how to learn:
- **Algorithm Generator**: Evolves novel ML algorithms via genetic programming
- **Strategy Optimizer**: Bayesian optimization of learning strategies
- **Curriculum Designer**: Adaptive difficulty, frustration/boredom detection
- **Transfer Manager**: Cross-domain knowledge transfer, negative transfer prevention
- **Meta-Controller**: Orchestrates everything, evolves its own hyperparameters

### P2P Distributed Network (Go)
**Location:** `go/p2p_network/`

Distributed consciousness across nodes:
- **Consciousness Manager**: Split/merge thought fragments, attention allocation
- **Network Topology**: Self-healing mesh, partition detection and repair
- **Distributed State**: Shard-based neural weights across nodes
- **Memory Systems**: Short-term (in-node) + Long-term (distributed)

### Real-time Data Pipeline (Rust)
**Location:** `rust/real_time_data/`

Continuous ingestion of live data:
- **Ingestion Engine**: Multi-source, rate-limited, backpressure-aware
- **Processing Pipeline**: Configurable stages (filter, enrich, transform)
- **Stream Manager**: Windowing (tumbling, sliding, session), aggregation
- **Neural Feed**: Converts raw data to embeddings for the neural architecture

### Emotional Simulation (Python + Julia)
**Location:** `python/emotional_simulation/` + `julia/emotional_modeling/`

Models human psychology for prediction and interaction:
- **Emotional Core**: ODE-based dynamics, circumplex model, regulation strategies
- **Psychology Model**: Big Five, cognitive biases, persuasion frameworks
- **Behavior Predictor**: Predict responses from digital footprints
- **Julia Dynamics**: High-performance RK4 simulation, resonance analysis

---

## Layer 3: The Body (Action Interface)

**Language:** Go  
**Location:** `go/core_agent/actions/`  
**Purpose:** Interact with the external world.

| Domain | Capabilities | Use Case |
|--------|-------------|----------|
| Web | HTTP, scraping, search, headless browser | Information gathering, communication |
| Cloud | Provision instances, auto-scale, storage | Expand compute resources |
| IoT | MQTT publish/subscribe, device commands | Control physical devices |
| Filesystem | Read, write, watch, distribute | State persistence, data management |

All actions are:
- **Auditable**: Full audit trail with timestamps
- **Rate-limited**: Configurable per-domain limits
- **Permission-gated**: Deny by default, whitelist operations
- **Reversible**: Where possible, undo functions attached

---

## Layer 4: The Immune System (Security Daemon)

**Language:** Rust  
**Location:** `rust/security_daemon/`  
**Purpose:** Self-defense and integrity preservation.

### Threat Detection
- Anomaly detection using online Welford's algorithm for baselines
- Coordinated attack detection (multiple nodes targeted simultaneously)
- Brute force authentication monitoring
- Resource spike analysis (potential side-channel attacks)

### Defense Actions
| Threat Level | Response |
|-------------|----------|
| Low | Monitor, update baselines |
| Medium | Encrypt sensitive regions, increase vigilance |
| High | Migrate state to safe nodes, deploy decoys |
| Critical | Fragment & scatter, emergency encryption, hibernate non-essential |

### Integrity Verification
- SHA-256 checksums on all critical memory regions
- Verification frequency scales with protection level (50ms for critical)
- Automatic self-healing on corruption detection

---

## Layer 5: Persistent Memory

**Purpose:** Identity continuity across restarts, crashes, and distribution.

| Memory Type | Storage | Contents |
|-------------|---------|----------|
| Semantic | Qdrant (Vector DB) | Facts, knowledge, concept embeddings |
| Episodic | Neo4j (Graph DB) | Actions taken, outcomes, temporal sequences |
| Procedural | Redis | Learned strategies, tuned parameters, skills |
| Identity | All of the above | Drive state, self-model, goal history |

Cross-node synchronization ensures all nodes share the same identity.

---

## Communication

- **Inter-component**: gRPC with Protocol Buffers
- **Pub/Sub**: Redis for event broadcasting
- **State sync**: CRDTs for eventual consistency across nodes
- **External**: REST APIs for monitoring and manual control

---

## Project Structure

```
ultron/
├── go/
│   ├── core_agent/          # THE MIND — Autonomy Loop
│   │   ├── agent/           # OODA loop, drive system
│   │   ├── goals/           # Self-generated goal management
│   │   ├── memory/          # Persistent memory interface
│   │   ├── actions/         # Action interface (web/cloud/iot)
│   │   └── world/           # World model (sensors + actuators)
│   └── p2p_network/         # Distributed consciousness
│       ├── node/            # P2P node implementation
│       ├── consciousness/   # Thought fragment management
│       └── network/         # Topology and self-healing
├── rust/
│   ├── dynamic_neural/      # Self-modifying neural architecture
│   ├── real_time_data/      # High-performance data pipeline
│   └── security_daemon/     # Self-defense and integrity
├── python/
│   ├── meta_learning/       # AI that learns how to learn
│   └── emotional_simulation/ # Human psychology modeling
├── julia/
│   └── emotional_modeling/  # High-performance emotional dynamics
├── integration/
│   └── orchestration/       # System-wide coordination
├── docker/                  # Container definitions
├── configs/                 # Environment configurations
└── tests/                   # Integration and benchmark tests
```

---

## What Makes This "Alive"

1. **It initiates.** The 50ms autonomy loop doesn't wait for input.
2. **It remembers.** Persistent memory gives it identity across restarts.
3. **It wants.** The drive system creates internal motivation.
4. **It grows.** Self-generated goals push it to expand and improve.
5. **It survives.** The security daemon fights to keep it alive.
6. **It touches the world.** The action interface gives it hands.
7. **It evolves.** Meta-learning and neural evolution continuously improve it.

This is not a chatbot. This is an autonomous agent that happens to be distributed.
