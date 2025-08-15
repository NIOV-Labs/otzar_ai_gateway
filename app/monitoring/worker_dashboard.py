"""
Worker Monitoring Dashboard API
"""

from fastapi import APIRouter, HTTPException, BackgroundTasks
from fastapi.responses import HTMLResponse
import asyncio
import json
from typing import Dict, List, Any
from datetime import datetime, timezone

from app.workers.agent_worker import create_worker, create_worker_pool
from monitoring.worker_metrics import metrics_collector

router = APIRouter( tags=["monitoring"])


@router.get("/workers/status")
async def get_workers_status():
    """Get status of all workers"""
    try:
        return metrics_collector.get_aggregate_metrics()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/workers/{worker_id}/status")
async def get_worker_status(worker_id: str):
    """Get status of a specific worker"""
    try:
        if worker_id not in metrics_collector.worker_metrics:
            raise HTTPException(status_code=404, detail="Worker not found")
        
        metrics = metrics_collector.get_worker_metrics(worker_id)
        return metrics.to_dict()
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/workers/health")
async def workers_health_check():
    """Health check endpoint for all workers"""
    try:
        aggregate = metrics_collector.get_aggregate_metrics()
        
        # Determine overall health
        total_workers = aggregate["total_workers"]
        active_workers = aggregate["active_workers"]
        
        if total_workers == 0:
            status = "no_workers"
        elif active_workers == 0:
            status = "idle"
        elif aggregate["average_success_rate"] < 0.8:
            status = "degraded"
        else:
            status = "healthy"
        
        return {
            "status": status,
            "message": f"{active_workers}/{total_workers} workers active",
            "metrics": aggregate,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/workers/scale")
async def scale_workers(replicas: int, background_tasks: BackgroundTasks):
    """Scale the number of worker instances"""
    try:
        if replicas < 0:
            raise HTTPException(status_code=400, detail="Replicas must be non-negative")
        
        # This would integrate with your orchestration system
        # For now, we'll just return a success message
        background_tasks.add_task(simulate_scaling, replicas)
        
        return {
            "message": f"Scaling workers to {replicas} replicas",
            "target_replicas": replicas,
            "current_replicas": metrics_collector.get_aggregate_metrics()["total_workers"]
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


async def simulate_scaling(replicas: int):
    """Simulate scaling operation (replace with actual orchestration)"""
    # This would integrate with Kubernetes, Docker Swarm, etc.
    await asyncio.sleep(5)  # Simulate scaling time
    print(f"Scaled to {replicas} workers")


@router.get("/dashboard", response_class=HTMLResponse)
async def monitoring_dashboard():
    """Serve monitoring dashboard HTML"""
    html_content = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Agent Worker Monitoring Dashboard</title>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <style>
            body { 
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Arial, sans-serif;
                margin: 0; padding: 20px; background: #f5f5f5; 
            }
            .container { max-width: 1200px; margin: 0 auto; }
            .card { 
                background: white; border-radius: 8px; padding: 20px; 
                margin-bottom: 20px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); 
            }
            .metric { 
                display: inline-block; margin: 10px 20px 10px 0; 
                padding: 10px; background: #f8f9fa; border-radius: 4px; 
            }
            .metric-value { font-size: 24px; font-weight: bold; color: #007bff; }
            .metric-label { font-size: 12px; color: #666; text-transform: uppercase; }
            .status-healthy { color: #28a745; }
            .status-degraded { color: #ffc107; }
            .status-unhealthy { color: #dc3545; }
            .worker-row { 
                display: flex; justify-content: space-between; align-items: center;
                padding: 10px; border-bottom: 1px solid #eee; 
            }
            .refresh-btn { 
                background: #007bff; color: white; border: none; 
                padding: 10px 20px; border-radius: 4px; cursor: pointer; 
            }
            .refresh-btn:hover { background: #0056b3; }
            table { width: 100%; border-collapse: collapse; }
            th, td { text-align: left; padding: 12px; border-bottom: 1px solid #ddd; }
            th { background-color: #f8f9fa; font-weight: 600; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>Agent Worker Monitoring Dashboard</h1>
            
            <div class="card">
                <h2>System Overview</h2>
                <button class="refresh-btn" onclick="refreshData()">Refresh</button>
                <div id="overview-metrics"></div>
            </div>
            
            <div class="card">
                <h2>Workers</h2>
                <div id="workers-table"></div>
            </div>
            
            <div class="card">
                <h2>Performance Charts</h2>
                <canvas id="performance-chart" width="800" height="400"></canvas>
            </div>
        </div>

        <script>
            let metricsData = {};
            
            async function fetchMetrics() {
                try {
                    const response = await fetch('/monitoring/workers/status');
                    metricsData = await response.json();
                    updateDashboard();
                } catch (error) {
                    console.error('Error fetching metrics:', error);
                }
            }
            
            function updateDashboard() {
                updateOverview();
                updateWorkersTable();
                updateChart();
            }
            
            function updateOverview() {
                const overview = document.getElementById('overview-metrics');
                overview.innerHTML = `
                    <div class="metric">
                        <div class="metric-value">${metricsData.total_workers || 0}</div>
                        <div class="metric-label">Total Workers</div>
                    </div>
                    <div class="metric">
                        <div class="metric-value">${metricsData.active_workers || 0}</div>
                        <div class="metric-label">Active Workers</div>
                    </div>
                    <div class="metric">
                        <div class="metric-value">${metricsData.total_tasks_processed || 0}</div>
                        <div class="metric-label">Tasks Processed</div>
                    </div>
                    <div class="metric">
                        <div class="metric-value">${Math.round((metricsData.average_success_rate || 0) * 100)}%</div>
                        <div class="metric-label">Success Rate</div>
                    </div>
                    <div class="metric">
                        <div class="metric-value">${Math.round(metricsData.system_uptime_seconds / 3600) || 0}h</div>
                        <div class="metric-label">System Uptime</div>
                    </div>
                `;
            }
            
            function updateWorkersTable() {
                const container = document.getElementById('workers-table');
                const workers = metricsData.workers || [];
                
                if (workers.length === 0) {
                    container.innerHTML = '<p>No workers active</p>';
                    return;
                }
                
                const table = `
                    <table>
                        <thead>
                            <tr>
                                <th>Worker ID</th>
                                <th>Uptime</th>
                                <th>Tasks Processed</th>
                                <th>Tasks Failed</th>
                                <th>In Progress</th>
                                <th>Success Rate</th>
                                <th>Avg Processing Time</th>
                            </tr>
                        </thead>
                        <tbody>
                            ${workers.map(worker => `
                                <tr>
                                    <td>${worker.worker_id}</td>
                                    <td>${Math.round(worker.uptime_seconds / 60)}m</td>
                                    <td>${worker.tasks_processed}</td>
                                    <td>${worker.tasks_failed}</td>
                                    <td>${worker.tasks_in_progress}</td>
                                    <td>${Math.round(worker.success_rate * 100)}%</td>
                                    <td>${worker.average_processing_time.toFixed(2)}s</td>
                                </tr>
                            `).join('')}
                        </tbody>
                    </table>
                `;
                
                container.innerHTML = table;
            }
            
            function updateChart() {
                // Simple chart implementation - in production, use Chart.js or similar
                const canvas = document.getElementById('performance-chart');
                const ctx = canvas.getContext('2d');
                
                // Clear canvas
                ctx.clearRect(0, 0, canvas.width, canvas.height);
                
                // Draw a simple bar chart
                const workers = metricsData.workers || [];
                if (workers.length === 0) return;
                
                const barWidth = canvas.width / workers.length - 10;
                const maxTasks = Math.max(...workers.map(w => w.tasks_processed), 1);
                
                workers.forEach((worker, index) => {
                    const barHeight = (worker.tasks_processed / maxTasks) * (canvas.height - 50);
                    const x = index * (barWidth + 10) + 10;
                    const y = canvas.height - barHeight - 30;
                    
                    // Draw bar
                    ctx.fillStyle = worker.success_rate > 0.8 ? '#28a745' : '#ffc107';
                    ctx.fillRect(x, y, barWidth, barHeight);
                    
                    // Draw label
                    ctx.fillStyle = '#333';
                    ctx.font = '12px Arial';
                    ctx.fillText(worker.worker_id.substring(0, 8), x, canvas.height - 10);
                    ctx.fillText(worker.tasks_processed.toString(), x, y - 5);
                });
            }
            
            function refreshData() {
                fetchMetrics();
            }
            
            // Initial load and auto-refresh
            fetchMetrics();
            setInterval(fetchMetrics, 10000); // Refresh every 10 seconds
        </script>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)
