"""
Metrics collection for Agent Workers
"""

import time
import asyncio
from typing import Dict, Any
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone


@dataclass
class WorkerMetrics:
    """Metrics for a single worker"""
    worker_id: str
    start_time: datetime = field(default_factory=datetime.now(timezone.utc))
    tasks_processed: int = 0
    tasks_failed: int = 0
    tasks_in_progress: int = 0
    total_processing_time: float = 0.0
    last_activity: datetime = field(default_factory=datetime.now(timezone.utc))
    
    def add_task_completion(self, processing_time: float, success: bool = True):
        """Record a completed task"""
        if success:
            self.tasks_processed += 1
        else:
            self.tasks_failed += 1
            
        self.total_processing_time += processing_time
        self.last_activity = datetime.now(timezone.utc)
    
    def start_task(self):
        """Record a task starting"""
        self.tasks_in_progress += 1
        self.last_activity = datetime.now(timezone.utc)
    
    def end_task(self):
        """Record a task ending"""
        self.tasks_in_progress = max(0, self.tasks_in_progress - 1)
    
    @property
    def uptime(self) -> timedelta:
        """Get worker uptime"""
        return datetime.now(timezone.utc) - self.start_time
    
    @property
    def average_processing_time(self) -> float:
        """Get average processing time per task"""
        total_tasks = self.tasks_processed + self.tasks_failed
        return self.total_processing_time / total_tasks if total_tasks > 0 else 0.0
    
    @property
    def success_rate(self) -> float:
        """Get task success rate"""
        total_tasks = self.tasks_processed + self.tasks_failed
        return self.tasks_processed / total_tasks if total_tasks > 0 else 1.0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            "worker_id": self.worker_id,
            "uptime_seconds": self.uptime.total_seconds(),
            "tasks_processed": self.tasks_processed,
            "tasks_failed": self.tasks_failed,
            "tasks_in_progress": self.tasks_in_progress,
            "average_processing_time": self.average_processing_time,
            "success_rate": self.success_rate,
            "last_activity": self.last_activity.isoformat(),
            "start_time": self.start_time.isoformat()
        }


class MetricsCollector:
    """Collects and aggregates metrics from multiple workers"""
    
    def __init__(self):
        self.worker_metrics: Dict[str, WorkerMetrics] = {}
        self.global_start_time = datetime.now(timezone.utc)
    
    def get_worker_metrics(self, worker_id: str) -> WorkerMetrics:
        """Get or create metrics for a worker"""
        if worker_id not in self.worker_metrics:
            self.worker_metrics[worker_id] = WorkerMetrics(worker_id=worker_id)
        return self.worker_metrics[worker_id]
    
    def remove_worker(self, worker_id: str):
        """Remove metrics for a worker"""
        self.worker_metrics.pop(worker_id, None)
    
    def get_aggregate_metrics(self) -> Dict[str, Any]:
        """Get aggregated metrics across all workers"""
        if not self.worker_metrics:
            return {
                "total_workers": 0,
                "total_tasks_processed": 0,
                "total_tasks_failed": 0,
                "total_tasks_in_progress": 0,
                "average_success_rate": 0.0,
                "system_uptime_seconds": (datetime.now(timezone.utc) - self.global_start_time).total_seconds()
            }
        
        total_processed = sum(m.tasks_processed for m in self.worker_metrics.values())
        total_failed = sum(m.tasks_failed for m in self.worker_metrics.values())
        total_in_progress = sum(m.tasks_in_progress for m in self.worker_metrics.values())
        
        # Calculate weighted average success rate
        success_rates = [m.success_rate for m in self.worker_metrics.values() if m.tasks_processed + m.tasks_failed > 0]
        avg_success_rate = sum(success_rates) / len(success_rates) if success_rates else 1.0
        
        return {
            "total_workers": len(self.worker_metrics),
            "active_workers": sum(1 for m in self.worker_metrics.values() if m.tasks_in_progress > 0),
            "total_tasks_processed": total_processed,
            "total_tasks_failed": total_failed,
            "total_tasks_in_progress": total_in_progress,
            "average_success_rate": avg_success_rate,
            "system_uptime_seconds": (datetime.now(timezone.utc) - self.global_start_time).total_seconds(),
            "workers": [m.to_dict() for m in self.worker_metrics.values()]
        }


# Global metrics collector
metrics_collector = MetricsCollector()
