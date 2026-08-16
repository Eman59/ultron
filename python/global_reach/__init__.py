"""
Ultron Global Reach Module — Omnicontinental-Scale Infrastructure Control.

This module extends Ultron's reach from a single cluster to global infrastructure:

  - SupplyChainAgent: Monitor and direct real-world logistics (ships, trucks,
    satellites, power grids) to support physical expansion.
  - CyberPhysicalEngine: Orchestrate simultaneous attacks across multiple
    domains (cyber + physical + social) as unified campaigns.

Integration:
  - Receives high-level directives from the Go agent's OODA loop
  - Coordinates with the ROS2 interface for physical operations
  - Uses the Rust data pipeline for real-time feed processing
  - Reports to the Python Learning Service for pattern recognition
"""

from .supply_chain import SupplyChainAgent
from .cyber_physical import CyberPhysicalEngine
