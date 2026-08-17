"""
Ultron Meta-Learning Engine

A system that learns how to learn - creates and optimizes its own learning algorithms.
"""

__version__: str = "0.1.0"
__author__: str = "Ultron AI Research Team"

from .algorithm_generator import AlgorithmGenerator
from .strategy_optimizer import StrategyOptimizer
from .curriculum_designer import CurriculumDesigner
from .transfer_manager import TransferManager
from .meta_controller import MetaController

__all__: list[str] = [
    "AlgorithmGenerator",
    "StrategyOptimizer", 
    "CurriculumDesigner",
    "TransferManager",
    "MetaController",
]