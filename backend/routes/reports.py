from fastapi import APIRouter

from backend.services.report_service import ReportService

router = APIRouter()
service = ReportService()


@router.get("/")
def list_reports():
    return service.export_manifest()


@router.post("/prediction")
def create_prediction_report(prediction: dict):
    return service.build_prediction_report(prediction)


@router.post("/{report_type}/export")
def export_report(report_type: str, payload: dict):
    return service.export_report(report_type=report_type, payload=payload)
