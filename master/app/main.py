from fastapi import FastAPI

from app.api import auth, deployments, engines, fs, gateway, huggingface, models, monitor, quantize, recommend, servers
from app.db.session import Base, SessionLocal, engine
from app.db.migrate import migrate
from app.config import settings
from app.services.auth import AuthMiddleware, seed_admin
from app.services.monitor import start_monitor_thread

migrate()
Base.metadata.create_all(bind=engine)

seed_admin(SessionLocal())

app = FastAPI(title=settings.app_name, version="0.2.0")
app.add_middleware(AuthMiddleware)

app.include_router(auth.router)
app.include_router(servers.router)
app.include_router(engines.router)
app.include_router(models.router)
app.include_router(recommend.router)
app.include_router(deployments.router)
app.include_router(fs.router)
app.include_router(quantize.router)
app.include_router(huggingface.router)
app.include_router(gateway.router)
app.include_router(monitor.router)

start_monitor_thread()


@app.get("/")
def root():
    return {"service": "llm-deploy-master", "status": "ok"}
