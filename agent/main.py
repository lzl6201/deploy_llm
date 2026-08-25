import asyncio
import logging

import httpx

from config import settings
from engine_runner import EngineRunner, resolve_command
from gpu_collector import collect_node_info, get_ip

logger = logging.getLogger("agent")


async def register(http: httpx.AsyncClient) -> int:
    info = collect_node_info()
    resp = await http.post(
        f"{settings.master_url}/api/servers/register",
        json={"token": settings.agent_token, **info},
    )
    resp.raise_for_status()
    return resp.json()["id"]


async def heartbeat(http: httpx.AsyncClient, server_id: int) -> None:
    info = collect_node_info()
    await http.post(
        f"{settings.master_url}/api/servers/{server_id}/heartbeat",
        json={"token": settings.agent_token, "gpus": info["gpus"]},
    )


async def _wait_healthy(http: httpx.AsyncClient, url: str, timeout: int) -> bool:
    loop = asyncio.get_event_loop()
    deadline = loop.time() + timeout
    while loop.time() < deadline:
        try:
            r = await http.get(url, timeout=5)
            if r.status_code == 200:
                return True
        except Exception:
            pass
        await asyncio.sleep(2)
    return False


async def process_pending(
    http: httpx.AsyncClient, server_id: int, runner: EngineRunner
) -> None:
    resp = await http.get(
        f"{settings.master_url}/api/deployments/pending",
        params={"server_id": server_id},
    )
    resp.raise_for_status()
    for dep in resp.json():
        dep_id = dep["id"]
        if runner.is_running(dep_id):
            continue
        lc = dep["launch_config"]
        logger.info("launching deployment %s (engine=%s)", dep_id, dep["engine"])
        try:
            runner.launch(dep_id, lc["command"], lc["env"])
            url = f"http://127.0.0.1:{lc['port']}{lc['health_check_path']}"
            healthy = await _wait_healthy(http, url, settings.health_timeout)
            if healthy:
                endpoint = f"http://{get_ip()}:{lc['port']}"
                await http.post(
                    f"{settings.master_url}/api/deployments/{dep_id}/status",
                    json={"status": "running", "endpoint": endpoint},
                )
            else:
                await http.post(
                    f"{settings.master_url}/api/deployments/{dep_id}/status",
                    json={"status": "failed", "detail": "health check timeout"},
                )
                runner.stop(dep_id)
        except Exception as e:
            logger.exception("deploy %s failed", dep_id)
            await http.post(
                f"{settings.master_url}/api/deployments/{dep_id}/status",
                json={"status": "failed", "detail": str(e)},
            )


async def process_pending_quantize(http: httpx.AsyncClient, server_id: int) -> None:
    resp = await http.get(
        f"{settings.master_url}/api/quantize/pending",
        params={"server_id": server_id},
    )
    resp.raise_for_status()
    for job in resp.json():
        job_id = job["id"]
        command = resolve_command(job["command"])
        logger.info("running quantize job %s (%s)", job_id, job["target_quant"])
        await http.post(
            f"{settings.master_url}/api/quantize/{job_id}/status",
            json={"status": "running", "progress": 0.0},
        )
        try:
            proc = await asyncio.create_subprocess_exec(
                *command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
            )
            await proc.communicate()
            if proc.returncode == 0:
                await http.post(
                    f"{settings.master_url}/api/quantize/{job_id}/status",
                    json={
                        "status": "done",
                        "progress": 100.0,
                        "target_path": job["target_path"],
                    },
                )
            else:
                await http.post(
                    f"{settings.master_url}/api/quantize/{job_id}/status",
                    json={"status": "failed", "error": f"exit code {proc.returncode}"},
                )
        except Exception as e:
            logger.exception("quantize job %s failed", job_id)
            await http.post(
                f"{settings.master_url}/api/quantize/{job_id}/status",
                json={"status": "failed", "error": str(e)},
            )


async def main() -> None:
    runner = EngineRunner()
    # Agent 与内网 Master 直连，绕过系统/环境代理（避免走 127.0.0.1:7890 之类代理）
    async with httpx.AsyncClient(timeout=10, trust_env=False) as http:
        server_id = None
        while server_id is None:
            try:
                server_id = await register(http)
                logger.info("registered as server id=%s", server_id)
            except Exception as e:
                logger.warning("register failed: %s, retrying in 5s", e)
                await asyncio.sleep(5)

        while True:
            try:
                await heartbeat(http, server_id)
            except Exception as e:
                logger.warning("heartbeat failed: %s", e)
                try:
                    server_id = await register(http)
                except Exception:
                    pass

            try:
                await process_pending(http, server_id, runner)
            except Exception as e:
                logger.warning("pending poll failed: %s", e)

            try:
                await process_pending_quantize(http, server_id)
            except Exception as e:
                logger.warning("quantize poll failed: %s", e)

            await asyncio.sleep(settings.heartbeat_interval)


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    asyncio.run(main())
