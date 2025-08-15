"""
CLI tool for managing agent workers
"""

import click
import asyncio
import json
import aiohttp
from typing import Optional


@click.group()
def worker_cli():
    """Agent Worker Management CLI"""
    pass


@worker_cli.command()
@click.option('--worker-id', help='Specific worker ID to check')
@click.option('--api-url', default='http://localhost:8000', help='API base URL')
def status(worker_id: Optional[str], api_url: str):
    """Get worker status"""
    async def get_status():
        async with aiohttp.ClientSession() as session:
            if worker_id:
                url = f"{api_url}/monitoring/workers/{worker_id}/status"
            else:
                url = f"{api_url}/monitoring/workers/status"
            
            async with session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    print(json.dumps(data, indent=2))
                else:
                    click.echo(f"Error: {response.status}")
    
    asyncio.run(get_status())


@worker_cli.command()
@click.argument('replicas', type=int)
@click.option('--api-url', default='http://localhost:8000', help='API base URL')
def scale(replicas: int, api_url: str):
    """Scale workers to specified number of replicas"""
    async def scale_workers():
        async with aiohttp.ClientSession() as session:
            url = f"{api_url}/monitoring/workers/scale"
            
            async with session.post(url, json={'replicas': replicas}) as response:
                if response.status == 200:
                    data = await response.json()
                    click.echo(f"✅ {data['message']}")
                else:
                    click.echo(f"❌ Error: {response.status}")
    
    asyncio.run(scale_workers())


@worker_cli.command()
@click.option('--api-url', default='http://localhost:8000', help='API base URL')
def health(api_url: str):
    """Check worker health"""
    async def check_health():
        async with aiohttp.ClientSession() as session:
            url = f"{api_url}/monitoring/workers/health"
            
            async with session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    status = data['status']
                    if status == 'healthy':
                        click.echo(f"✅ Workers are healthy: {data['message']}")
                    else:
                        click.echo(f"⚠️ Workers status: {status} - {data['message']}")
                else:
                    click.echo(f"❌ Health check failed: {response.status}")
    
    asyncio.run(check_health())


@worker_cli.command()
@click.option('--follow', '-f', is_flag=True, help='Follow log output')
@click.option('--worker-id', help='Filter by worker ID')
def logs(follow: bool, worker_id: Optional[str]):
    """View worker logs"""
    if worker_id:
        click.echo(f"Showing logs for worker: {worker_id}")
    else:
        click.echo("Showing logs for all workers")
    
    # This would integrate with your logging system
    # For now, just show a message
    click.echo("Log integration not implemented - check your logging system")


if __name__ == '__main__':
    worker_cli()
