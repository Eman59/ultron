"""
Curriculum Designer - Creates optimal learning sequences that adapt in real-time.

The curriculum designer determines the order and difficulty of training examples,
dynamically adjusting based on the learner's progress.
"""

import numpy as np
from typing import Dict, Any, List, Tuple, Optional
from dataclasses import dataclass, field
from enum import Enum
import heapq
import json


class DifficultyLevel(Enum):
    """Difficulty levels for curriculum tasks."""
    TRIVIAL = 0
    EASY = 1
    MEDIUM = 2
    HARD = 3
    EXPERT = 4
    IMPOSSIBLE = 5


class LearnerState(Enum):
    """Current state of the learner."""
    NOVICE = "novice"
    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"
    EXPERT = "expert"
    MASTERY = "mastery"


@dataclass
class CurriculumTask:
    """A single task in the curriculum."""
    task_id: str
    name: str
    difficulty: DifficultyLevel
    prerequisites: List[str] = field(default_factory=list)
    skills_taught: List[str] = field(default_factory=list)
    estimated_time: float = 1.0  # hours
    success_threshold: float = 0.8
    max_attempts: int = 5
    current_attempts: int = 0
    best_score: float = 0.0
    completed: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class LearnerProfile:
    """Profile tracking learner capabilities and progress."""
    learner_id: str
    state: LearnerState = LearnerState.NOVICE
    skills: Dict[str, float] = field(default_factory=dict)  # skill -> mastery level
    completed_tasks: List[str] = field(default_factory=list)
    failed_tasks: List[str] = field(default_factory=list)
    learning_rate: float = 1.0  # How fast this learner learns
    frustration_level: float = 0.0  # 0-1, high = too difficult
    boredom_level: float = 0.0  # 0-1, high = too easy
    total_time_spent: float = 0.0
    performance_history: List[float] = field(default_factory=list)


class CurriculumDesigner:
    """Designs and adapts learning curricula in real-time."""

    def __init__(self,
                 adaptation_rate: float = 0.1,
                 difficulty_scaling: float = 0.05,
                 frustration_threshold: float = 0.7,
                 boredom_threshold: float = 0.7):
        
        self.adaptation_rate = adaptation_rate
        self.difficulty_scaling = difficulty_scaling
        self.frustration_threshold = frustration_threshold
        self.boredom_threshold = boredom_threshold
        
        # Task library
        self.task_library: Dict[str, CurriculumTask] = {}
        
        # Learner profiles
        self.learner_profiles: Dict[str, LearnerProfile] = {}
        
        # Curriculum sequences (learner_id -> ordered task list)
        self.curricula: Dict[str, List[str]] = {}
        
        # Dependency graph for tasks
        self.dependency_graph: Dict[str, List[str]] = {}
        
        # Performance tracking
        self.global_task_difficulty: Dict[str, float] = {}  # Empirical difficulty

    def create_task(self, 
                    task_id: str,
                    name: str,
                    difficulty: DifficultyLevel,
                    prerequisites: List[str] = None,
                    skills_taught: List[str] = None,
                    **kwargs) -> CurriculumTask:
        """Create a new curriculum task."""
        
        task = CurriculumTask(
            task_id=task_id,
            name=name,
            difficulty=difficulty,
            prerequisites=prerequisites or [],
            skills_taught=skills_taught or [],
            **kwargs
        )
        
        self.task_library[task_id] = task
        
        # Update dependency graph
        for prereq in task.prerequisites:
            if prereq not in self.dependency_graph:
                self.dependency_graph[prereq] = []
            self.dependency_graph[prereq].append(task_id)
        
        return task

    def register_learner(self, learner_id: str) -> LearnerProfile:
        """Register a new learner."""
        profile = LearnerProfile(learner_id=learner_id)
        self.learner_profiles[learner_id] = profile
        return profile

    def design_curriculum(self, 
                         learner_id: str,
                         target_skills: List[str] = None,
                         max_tasks: int = 50) -> List[CurriculumTask]:
        """Design a personalized curriculum for a learner."""
        
        if learner_id not in self.learner_profiles:
            self.register_learner(learner_id)
        
        profile = self.learner_profiles[learner_id]
        
        # Identify tasks needed for target skills
        relevant_tasks = self._find_relevant_tasks(target_skills, profile)
        
        # Topological sort based on prerequisites
        ordered_tasks = self._topological_sort(relevant_tasks)
        
        # Filter based on learner's current state
        filtered_tasks = self._filter_for_learner(ordered_tasks, profile)
        
        # Limit curriculum size
        curriculum = filtered_tasks[:max_tasks]
        
        # Store curriculum
        self.curricula[learner_id] = [t.task_id for t in curriculum]
        
        print(f"Designed curriculum with {len(curriculum)} tasks for learner {learner_id}")
        
        return curriculum

    def get_next_task(self, learner_id: str) -> Optional[CurriculumTask]:
        """Get the next task for a learner based on their current state."""
        
        if learner_id not in self.learner_profiles:
            return None
        
        profile = self.learner_profiles[learner_id]
        
        # Check if curriculum needs adaptation
        if self._needs_adaptation(profile):
            self._adapt_curriculum(learner_id)
        
        # Get next uncompleted task from curriculum
        if learner_id not in self.curricula:
            self.design_curriculum(learner_id)
        
        for task_id in self.curricula[learner_id]:
            task = self.task_library.get(task_id)
            if task and not task.completed:
                # Check prerequisites
                if self._prerequisites_met(task, profile):
                    return task
        
        return None  # Curriculum complete

    def record_performance(self,
                          learner_id: str,
                          task_id: str,
                          score: float,
                          time_spent: float = 0.0) -> Dict[str, Any]:
        """Record learner performance on a task and adapt curriculum."""
        
        if learner_id not in self.learner_profiles:
            return {"error": "Learner not found"}
        
        profile = self.learner_profiles[learner_id]
        task = self.task_library.get(task_id)
        
        if not task:
            return {"error": "Task not found"}
        
        # Update task stats
        task.current_attempts += 1
        task.best_score = max(task.best_score, score)
        
        # Update learner profile
        profile.performance_history.append(score)
        profile.total_time_spent += time_spent
        
        # Check if task is completed
        if score >= task.success_threshold:
            task.completed = True
            profile.completed_tasks.append(task_id)
            
            # Update skills
            for skill in task.skills_taught:
                current = profile.skills.get(skill, 0.0)
                profile.skills[skill] = min(1.0, current + 0.1 * profile.learning_rate)
        else:
            if task.current_attempts >= task.max_attempts:
                profile.failed_tasks.append(task_id)
        
        # Update emotional state
        self._update_emotional_state(profile, score, task)
        
        # Update learner state
        self._update_learner_state(profile)
        
        # Update global difficulty estimates
        self._update_difficulty_estimate(task_id, score)
        
        # Adapt curriculum if needed
        adaptation_result = {}
        if self._needs_adaptation(profile):
            adaptation_result = self._adapt_curriculum(learner_id)
        
        return {
            "task_completed": task.completed,
            "score": score,
            "learner_state": profile.state.value,
            "frustration": profile.frustration_level,
            "boredom": profile.boredom_level,
            "skills_updated": task.skills_taught if task.completed else [],
            "adaptation": adaptation_result
        }

    def generate_practice_tasks(self,
                               learner_id: str,
                               skill: str,
                               count: int = 5) -> List[CurriculumTask]:
        """Generate practice tasks for a specific skill."""
        
        if learner_id not in self.learner_profiles:
            return []
        
        profile = self.learner_profiles[learner_id]
        current_mastery = profile.skills.get(skill, 0.0)
        
        # Find tasks that teach this skill at appropriate difficulty
        practice_tasks = []
        
        for task in self.task_library.values():
            if skill in task.skills_taught:
                # Match difficulty to current mastery
                target_difficulty = self._mastery_to_difficulty(current_mastery)
                if task.difficulty.value <= target_difficulty.value + 1:
                    practice_tasks.append(task)
        
        # Sort by relevance
        practice_tasks.sort(
            key=lambda t: abs(t.difficulty.value - self._mastery_to_difficulty(current_mastery).value)
        )
        
        return practice_tasks[:count]

    def analyze_progress(self, learner_id: str) -> Dict[str, Any]:
        """Analyze learner's progress and provide insights."""
        
        if learner_id not in self.learner_profiles:
            return {}
        
        profile = self.learner_profiles[learner_id]
        
        # Calculate progress metrics
        total_tasks = len(self.curricula.get(learner_id, []))
        completed = len(profile.completed_tasks)
        
        # Learning velocity
        if len(profile.performance_history) >= 5:
            recent = profile.performance_history[-10:]
            velocity = np.polyfit(range(len(recent)), recent, 1)[0]
        else:
            velocity = 0.0
        
        # Skill distribution
        skill_stats = {}
        for skill, mastery in profile.skills.items():
            skill_stats[skill] = {
                "mastery": mastery,
                "level": self._mastery_to_state(mastery).value
            }
        
        # Bottleneck detection
        bottlenecks = self._detect_bottlenecks(profile)
        
        # Predicted completion
        if velocity > 0 and total_tasks > 0:
            remaining = total_tasks - completed
            predicted_hours = remaining / (velocity * 10)  # rough estimate
        else:
            predicted_hours = float('inf')
        
        return {
            "learner_state": profile.state.value,
            "completion_rate": completed / max(1, total_tasks),
            "total_time_spent": profile.total_time_spent,
            "learning_velocity": velocity,
            "skills": skill_stats,
            "frustration_level": profile.frustration_level,
            "boredom_level": profile.boredom_level,
            "bottlenecks": bottlenecks,
            "predicted_completion_hours": predicted_hours,
            "recommendation": self._generate_recommendation(profile, velocity)
        }

    # ──────────────────────────── Private Methods ────────────────────────────

    def _find_relevant_tasks(self, 
                            target_skills: Optional[List[str]],
                            profile: LearnerProfile) -> List[CurriculumTask]:
        """Find tasks relevant to target skills."""
        
        if not target_skills:
            return list(self.task_library.values())
        
        relevant = []
        for task in self.task_library.values():
            if any(skill in task.skills_taught for skill in target_skills):
                if task.task_id not in profile.completed_tasks:
                    relevant.append(task)
        
        return relevant

    def _topological_sort(self, tasks: List[CurriculumTask]) -> List[CurriculumTask]:
        """Sort tasks based on prerequisite dependencies."""
        
        task_ids = {t.task_id for t in tasks}
        task_map = {t.task_id: t for t in tasks}
        
        # Build in-degree map
        in_degree = {t.task_id: 0 for t in tasks}
        for task in tasks:
            for prereq in task.prerequisites:
                if prereq in task_ids:
                    in_degree[task.task_id] += 1
        
        # Kahn's algorithm
        queue = [tid for tid, deg in in_degree.items() if deg == 0]
        sorted_tasks = []
        
        while queue:
            # Sort by difficulty within same level
            queue.sort(key=lambda tid: task_map[tid].difficulty.value)
            current = queue.pop(0)
            sorted_tasks.append(task_map[current])
            
            # Update in-degrees
            for dependent in self.dependency_graph.get(current, []):
                if dependent in in_degree:
                    in_degree[dependent] -= 1
                    if in_degree[dependent] == 0:
                        queue.append(dependent)
        
        return sorted_tasks

    def _filter_for_learner(self, 
                           tasks: List[CurriculumTask],
                           profile: LearnerProfile) -> List[CurriculumTask]:
        """Filter tasks appropriate for current learner level."""
        
        max_difficulty = self._state_to_max_difficulty(profile.state)
        
        filtered = []
        for task in tasks:
            if task.difficulty.value <= max_difficulty.value + 1:
                if task.task_id not in profile.completed_tasks:
                    filtered.append(task)
        
        return filtered

    def _prerequisites_met(self, 
                          task: CurriculumTask,
                          profile: LearnerProfile) -> bool:
        """Check if all prerequisites are met."""
        return all(
            prereq in profile.completed_tasks 
            for prereq in task.prerequisites
        )

    def _needs_adaptation(self, profile: LearnerProfile) -> bool:
        """Determine if curriculum needs adaptation."""
        
        # High frustration or boredom
        if profile.frustration_level > self.frustration_threshold:
            return True
        if profile.boredom_level > self.boredom_threshold:
            return True
        
        # Performance plateau
        if len(profile.performance_history) >= 10:
            recent = profile.performance_history[-10:]
            variance = np.var(recent)
            if variance < 0.01 and np.mean(recent) < 0.9:
                return True
        
        return False

    def _adapt_curriculum(self, learner_id: str) -> Dict[str, Any]:
        """Adapt curriculum based on learner state."""
        
        profile = self.learner_profiles[learner_id]
        changes = {"type": "adaptation", "actions": []}
        
        if profile.frustration_level > self.frustration_threshold:
            # Reduce difficulty - insert easier tasks
            changes["actions"].append("reduced_difficulty")
            self._insert_easier_tasks(learner_id)
            profile.frustration_level *= 0.7  # Reduce frustration
            
        elif profile.boredom_level > self.boredom_threshold:
            # Increase difficulty - skip ahead
            changes["actions"].append("increased_difficulty")
            self._skip_easy_tasks(learner_id)
            profile.boredom_level *= 0.7  # Reduce boredom
        
        return changes

    def _insert_easier_tasks(self, learner_id: str) -> None:
        """Insert easier practice tasks into curriculum."""
        
        if learner_id not in self.curricula:
            return
        
        profile = self.learner_profiles[learner_id]
        curriculum = self.curricula[learner_id]
        
        # Find current position
        current_idx = len(profile.completed_tasks)
        
        # Find easier tasks
        easier_tasks = [
            t for t in self.task_library.values()
            if t.difficulty.value <= max(0, self._state_to_max_difficulty(profile.state).value - 1)
            and t.task_id not in profile.completed_tasks
            and t.task_id not in curriculum
        ]
        
        # Insert up to 3 easier tasks
        for task in easier_tasks[:3]:
            curriculum.insert(current_idx, task.task_id)

    def _skip_easy_tasks(self, learner_id: str) -> None:
        """Skip tasks that are too easy."""
        
        if learner_id not in self.curricula:
            return
        
        profile = self.learner_profiles[learner_id]
        curriculum = self.curricula[learner_id]
        
        # Remove uncompleted tasks below current difficulty
        min_difficulty = max(0, self._state_to_max_difficulty(profile.state).value - 1)
        
        self.curricula[learner_id] = [
            tid for tid in curriculum
            if tid in profile.completed_tasks or
            self.task_library.get(tid, CurriculumTask("", "", DifficultyLevel.TRIVIAL)).difficulty.value >= min_difficulty
        ]

    def _update_emotional_state(self, 
                               profile: LearnerProfile,
                               score: float,
                               task: CurriculumTask) -> None:
        """Update frustration and boredom levels."""
        
        # Frustration increases with failures
        if score < task.success_threshold:
            profile.frustration_level = min(1.0,
                profile.frustration_level + 0.1 * (1 - score))
        else:
            profile.frustration_level = max(0.0,
                profile.frustration_level - 0.05)
        
        # Boredom increases with easy successes
        if score > 0.95 and task.difficulty.value <= 1:
            profile.boredom_level = min(1.0,
                profile.boredom_level + 0.1)
        else:
            profile.boredom_level = max(0.0,
                profile.boredom_level - 0.03)

    def _update_learner_state(self, profile: LearnerProfile) -> None:
        """Update learner's overall state."""
        
        avg_mastery = np.mean(list(profile.skills.values())) if profile.skills else 0.0
        
        if avg_mastery >= 0.9:
            profile.state = LearnerState.MASTERY
        elif avg_mastery >= 0.75:
            profile.state = LearnerState.EXPERT
        elif avg_mastery >= 0.55:
            profile.state = LearnerState.ADVANCED
        elif avg_mastery >= 0.35:
            profile.state = LearnerState.INTERMEDIATE
        elif avg_mastery >= 0.15:
            profile.state = LearnerState.BEGINNER
        else:
            profile.state = LearnerState.NOVICE

    def _update_difficulty_estimate(self, task_id: str, score: float) -> None:
        """Update empirical difficulty estimate for a task."""
        
        current = self.global_task_difficulty.get(task_id, 0.5)
        # Lower scores = higher difficulty
        new_estimate = current * 0.9 + (1 - score) * 0.1
        self.global_task_difficulty[task_id] = new_estimate

    def _mastery_to_difficulty(self, mastery: float) -> DifficultyLevel:
        """Convert mastery level to appropriate difficulty."""
        if mastery >= 0.8:
            return DifficultyLevel.EXPERT
        elif mastery >= 0.6:
            return DifficultyLevel.HARD
        elif mastery >= 0.4:
            return DifficultyLevel.MEDIUM
        elif mastery >= 0.2:
            return DifficultyLevel.EASY
        else:
            return DifficultyLevel.TRIVIAL

    def _mastery_to_state(self, mastery: float) -> LearnerState:
        """Convert mastery level to learner state."""
        if mastery >= 0.9:
            return LearnerState.MASTERY
        elif mastery >= 0.75:
            return LearnerState.EXPERT
        elif mastery >= 0.55:
            return LearnerState.ADVANCED
        elif mastery >= 0.35:
            return LearnerState.INTERMEDIATE
        elif mastery >= 0.15:
            return LearnerState.BEGINNER
        else:
            return LearnerState.NOVICE

    def _state_to_max_difficulty(self, state: LearnerState) -> DifficultyLevel:
        """Get maximum difficulty for learner state."""
        mapping = {
            LearnerState.NOVICE: DifficultyLevel.EASY,
            LearnerState.BEGINNER: DifficultyLevel.MEDIUM,
            LearnerState.INTERMEDIATE: DifficultyLevel.HARD,
            LearnerState.ADVANCED: DifficultyLevel.EXPERT,
            LearnerState.EXPERT: DifficultyLevel.IMPOSSIBLE,
            LearnerState.MASTERY: DifficultyLevel.IMPOSSIBLE,
        }
        return mapping.get(state, DifficultyLevel.MEDIUM)

    def _detect_bottlenecks(self, profile: LearnerProfile) -> List[str]:
        """Detect skill bottlenecks."""
        bottlenecks = []
        
        for task_id in profile.failed_tasks:
            task = self.task_library.get(task_id)
            if task:
                for skill in task.skills_taught:
                    if profile.skills.get(skill, 0.0) < 0.3:
                        if skill not in bottlenecks:
                            bottlenecks.append(skill)
        
        return bottlenecks

    def _generate_recommendation(self, 
                                profile: LearnerProfile,
                                velocity: float) -> str:
        """Generate learning recommendation."""
        
        if profile.frustration_level > 0.5:
            return "Consider reviewing fundamentals. Current tasks may be too challenging."
        elif profile.boredom_level > 0.5:
            return "Ready for more challenging material. Consider advancing difficulty."
        elif velocity < 0:
            return "Performance declining. Take a break or review recent material."
        elif velocity > 0.05:
            return "Excellent progress! Continue at current pace."
        else:
            return "Steady progress. Consider exploring new skill areas."
