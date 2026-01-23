from pathlib import Path

root_dir = Path(__file__).parent

data_dir = root_dir / "data"
vision_llm_dir = root_dir / "vision_llm"
app_dir = root_dir / "app"
ftp_uploads_dir = data_dir / "ftp_uploads"
# Legacy alias for backwards compatibility
viewer_dir = app_dir