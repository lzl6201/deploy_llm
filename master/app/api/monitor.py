from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.orm import Alert
from app.schemas.monitor import AlertOut, OverviewOut
from app.services import monitor

router = APIRouter(prefix="/api/monitor", tags=["monitor"])


@router.get("/overview", response_model=OverviewOut)
def get_overview(db: Session = Depends(get_db)):
    return monitor.overview(db)


@router.get("/alerts", response_model=list[AlertOut])
def list_alerts(open_only: bool = False, db: Session = Depends(get_db)):
    q = db.query(Alert).order_by(Alert.id.desc())
    if open_only:
        q = q.filter(Alert.status == "open")
    return q.limit(200).all()


@router.post("/alerts/{alert_id}/ack")
def ack_alert(alert_id: int, db: Session = Depends(get_db)):
    alert = db.get(Alert, alert_id)
    if alert is None:
        raise HTTPException(status_code=404, detail="alert not found")
    alert.status = "resolved"
    alert.resolved_at = datetime.utcnow()
    db.commit()
    return {"ok": True}
