from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict
from pathlib import Path

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # LLM Settings
    llm_model_name: str = "gpt-oss-20b"

    # Project Paths
    project_root: Path = Path.cwd()
    tests_output_dir: Path = Path("tests")
    analysis_output_file: Path = Path("analysis.json")
    results_output_file: Path = Path("results.json")
    report_output_file: Path = Path("test_report.html")
    xml_report_output_file: Path = Path("test_report.xml")
    coverage_output_file: Path = Path("coverage_report.html")

    # API Keys (example, not currently used but good practice)
    openai_api_key: Optional[str] = None

    # Thresholds (example)
    coverage_threshold: float = 80.0

settings = Settings()
