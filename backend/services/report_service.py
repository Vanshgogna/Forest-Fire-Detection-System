from datetime import datetime


class ReportService:
    def build_prediction_report(self, prediction: dict) -> dict:
        return {
            "title": "Prediction Intelligence Report",
            "generated_at": datetime.utcnow().isoformat(),
            "format_options": ["PDF", "CSV", "Excel", "JSON", "GeoJSON"],
            "summary": prediction,
        }

    def export_manifest(self) -> dict:
        return {"exports": ["prediction", "weather", "vegetation", "gis", "alerts", "executive"]}

    def export_report(self, report_type: str, payload: dict) -> dict:
        export_format = payload.get("format", "json").lower()
        supported = {"pdf", "csv", "xlsx", "excel", "json", "geojson"}
        if export_format not in supported:
            return {"status": "rejected", "reason": f"Unsupported export format: {export_format}", "supported": sorted(supported)}
        return {
            "status": "queued",
            "report_type": report_type,
            "format": export_format,
            "delivery": payload.get("delivery", "download"),
            "job_type": "report_generation",
        }
