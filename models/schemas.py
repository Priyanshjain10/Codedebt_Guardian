import uuid
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator, model_validator


class DebtSeverity(str, Enum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class DebtCategory(str, Enum):
    SECURITY = "security"
    PERFORMANCE = "performance"
    MAINTAINABILITY = "maintainability"
    COMPLEXITY = "complexity"
    DOCUMENTATION = "documentation"
    TESTING = "testing"
    DEPENDENCIES = "dependencies"


class EffortLevel(str, Enum):
    MINUTES = "MINUTES"
    HOURS = "HOURS"
    DAYS = "DAYS"


class Priority(str, Enum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class DetectionSource(str, Enum):
    STATIC_ANALYSIS = "static_analysis"
    GEMINI_AI = "gemini_ai"
    DEPENDENCY_CHECK = "dependency_analysis"
    DOCUMENTATION = "documentation_analysis"
    SATD_ANALYSIS = "satd_analysis"
    TEMPLATE = "template"
    FALLBACK = "fallback"


class CodeLocation(BaseModel):
    file_path: str
    line_start: Optional[int] = Field(None, ge=1)
    line_end: Optional[int] = Field(None, ge=1)
    function_name: Optional[str] = None
    class_name: Optional[str] = None

    @model_validator(mode="after")
    def validate_line_range(self) -> "CodeLocation":
        if self.line_start and self.line_end:
            if self.line_end < self.line_start:
                raise ValueError("line_end must be >= line_start")
        return self

    @classmethod
    def from_string(cls, location_str: str) -> "CodeLocation":
        if ":" in location_str:
            parts = location_str.rsplit(":", 1)
            try:
                return cls(file_path=parts[0], line_start=int(parts[1]))
            except ValueError:
                pass
        return cls(file_path=location_str)

    def to_string(self) -> str:
        return (
            f"{self.file_path}:{self.line_start}" if self.line_start else self.file_path
        )


class TechnicalDebt(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    type: str
    title: str = Field(default="")
    description: str
    category: DebtCategory = Field(default=DebtCategory.MAINTAINABILITY)
    severity: DebtSeverity
    location: CodeLocation
    impact: str = Field(default="")
    effort_to_fix: EffortLevel = Field(default=EffortLevel.HOURS)
    code_snippet: Optional[str] = None
    source: DetectionSource = Field(default=DetectionSource.STATIC_ANALYSIS)
    confidence: float = Field(default=0.9, ge=0.0, le=1.0)
    detected_at: datetime = Field(default_factory=datetime.now)

    # Filled by PriorityRankingAgent
    score: Optional[int] = Field(None, ge=0, le=100)
    priority: Optional[Priority] = None
    rank: Optional[int] = Field(None, ge=1)
    quick_win: bool = False
    blocks_other_work: bool = False
    business_justification: str = ""
    recommended_sprint: int = Field(default=2, ge=1, le=3)

    # THE FIX: use model_validator(mode="after") so it runs AFTER
    # all fields are assigned — catches empty string title correctly
    @model_validator(mode="after")
    def generate_title(self) -> "TechnicalDebt":
        if not self.title or not self.title.strip():
            self.title = self.type.replace("_", " ").title()
        return self

    @field_validator("description")
    @classmethod
    def description_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("description cannot be empty")
        return v.strip()

    model_config = {"use_enum_values": True}


class FixProposal(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    debt_id: Optional[str] = None
    issue_type: str
    severity: DebtSeverity
    problem_summary: str = Field(..., min_length=10)
    fix_summary: str = Field(..., min_length=10)
    before_code: str = ""
    after_code: str = ""
    steps: List[str] = Field(default_factory=list)
    testing_tip: str = "Run your test suite to verify the fix."
    estimated_time: str = "Unknown"
    references: List[str] = Field(default_factory=list)
    source: DetectionSource = Field(default=DetectionSource.GEMINI_AI)
    original_issue: Optional[Dict[str, Any]] = None

    @field_validator("steps")
    @classmethod
    def steps_not_empty(cls, v: List[str]) -> List[str]:
        return [s for s in v if s.strip()]

    model_config = {"use_enum_values": True}


class PullRequestInfo(BaseModel):
    number: int = Field(..., ge=1)
    title: str
    html_url: str
    state: str = "open"
    branch: str
    debt_type: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.now)

    @field_validator("html_url")
    @classmethod
    def validate_github_url(cls, v: str) -> str:
        if not v.startswith("https://github.com"):
            raise ValueError("html_url must be a GitHub URL")
        return v


class RepoMetadata(BaseModel):
    name: str
    full_name: str
    description: Optional[str] = None
    language: Optional[str] = None
    stars: int = 0
    forks: int = 0
    open_issues: int = 0
    size_kb: int = 0
    default_branch: str = "main"
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    topics: List[str] = Field(default_factory=list)
    license: Optional[str] = None
    has_wiki: bool = False


class DetectionStats(BaseModel):
    by_severity: Dict[str, int] = Field(default_factory=dict)
    by_type: Dict[str, int] = Field(default_factory=dict)
    by_source: Dict[str, int] = Field(default_factory=dict)
    by_category: Dict[str, int] = Field(default_factory=dict)


class DetectionResult(BaseModel):
    repo_url: str
    branch: str = "main"
    repo_metadata: RepoMetadata
    files_scanned: int = 0
    total_issues: int = 0
    issues: List[TechnicalDebt] = Field(default_factory=list)
    stats: DetectionStats = Field(default_factory=DetectionStats)
    detected_at: datetime = Field(default_factory=datetime.now)

    @model_validator(mode="after")
    def sync_total_issues(self) -> "DetectionResult":
        self.total_issues = len(self.issues)
        return self


class AnalysisSummary(BaseModel):
    total_issues: int = 0
    critical: int = 0
    high: int = 0
    medium: int = 0
    low: int = 0
    quick_wins: int = 0
    fixes_proposed: int = 0
    prs_created: int = 0
    files_scanned: int = 0
    estimated_hours_saved: float = 0.0

    @model_validator(mode="after")
    def validate_totals(self) -> "AnalysisSummary":
        computed = self.critical + self.high + self.medium + self.low
        if computed > self.total_issues:
            self.total_issues = computed
        return self


class AnalysisReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4())[:12])
    repo_url: str
    branch: str = "main"
    generated_at: datetime = Field(default_factory=datetime.now)
    duration_seconds: Optional[float] = None
    tool_version: str = "1.0.0"

    repo_metadata: Optional[RepoMetadata] = None
    summary: AnalysisSummary = Field(default_factory=AnalysisSummary)
    top_issues: List[TechnicalDebt] = Field(default_factory=list)
    fix_proposals: List[FixProposal] = Field(default_factory=list)
    pull_requests: List[PullRequestInfo] = Field(default_factory=list)
    stats: DetectionStats = Field(default_factory=DetectionStats)

    def to_dict(self) -> Dict[str, Any]:
        return self.model_dump(mode="json")

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AnalysisReport":
        return cls.model_validate(data)


class AgentMetrics(BaseModel):
    service: str
    total_spans: int = 0
    error_count: int = 0
    operations: Dict[str, Dict[str, float]] = Field(default_factory=dict)

    @property
    def error_rate(self) -> float:
        if self.total_spans == 0:
            return 0.0
        return round(self.error_count / self.total_spans * 100, 1)


class SystemMetrics(BaseModel):
    orchestrator: AgentMetrics
    detection_agent: AgentMetrics
    ranking_agent: AgentMetrics
    fix_agent: AgentMetrics
    memory_stats: Dict[str, Any] = Field(default_factory=dict)
    collected_at: datetime = Field(default_factory=datetime.now)
