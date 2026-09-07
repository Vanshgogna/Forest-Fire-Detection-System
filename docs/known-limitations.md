# Known Limitations

- The current UI uses realistic mock environmental datasets for product demonstration.
- Database persistence models and migrations are present, but several public read endpoints still use service-level mock data until real ingestion jobs are connected.
- Satellite processing currently returns reusable processing manifests and array utilities rather than downloading full Sentinel/MODIS/VIIRS scenes in the API process.
- Docker validation could not be completed on this local macOS 12 machine because Docker Desktop is unsupported and the Colima fallback install was interrupted.
- Email, SMS, and webhook notifications are represented as queue contracts and future provider integration points.
- Cloudinary is configured as an environment variable but media upload integration is not yet wired to a live account.
- Deep learning, drone imagery, and real-time satellite streams are future extensions.
- Production database, Redis, and object storage must be provisioned externally for real deployment.

These limitations are isolated behind service, repository, task, and configuration boundaries so future implementation can replace mock or manifest behavior without changing the main API contracts.
