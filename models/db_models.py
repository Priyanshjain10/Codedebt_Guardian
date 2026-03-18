"""
CodeDebt Guardian — SQLAlchemy ORM Models
Full multi-tenant SaaS schema: orgs → teams → projects → scans → issues.
"""

import uuid

class ScanStatus:
    PENDING = "pending"
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"

class ScanPhase:
    INIT = "init"
    DETECTION = "detection"
    RANKING = "ranking"
    FIX_GENERATION = "fix_generation"
    AUTOPILOT = "autopilot"


from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship
from pgvector.sqlalchemy import Vector

from database import Base


def _utcnow():
    return datetime.now(timezone.utc)


def _uuid():
    return uuid.uuid4()


# ═══════════════════════════════════════════════════════════════════════
# Organization / Team / User
# ═══════════════════════════════════════════════════════════════════════


class Organization(Base):
    __tablename__ = "organizations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    name = Column(String(255), nullable=False)
    slug = Column(String(255), unique=True, nullable=False, index=True)
    billing_email = Column(String(255))
    plan = Column(String(50), default="free")  # free | pro | enterprise
    settings = Column(JSONB, default=dict)
    created_at = Column(DateTime(timezone=True), default=_utcnow)
    updated_at = Column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)

    teams = relationship(
        "Team", back_populates="organization", cascade="all, delete-orphan"
    )
    subscriptions = relationship("Subscription", back_populates="organization")
    api_keys = relationship("APIKeyModel", back_populates="organization")
    webhooks = relationship("Webhook", back_populates="organization")
    usage_logs = relationship("UsageLog", back_populates="organization")
    github_installations = relationship(
        "GitHubInstallation",
        back_populates="organization",
        cascade="all, delete-orphan",
    )


class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=True)  # null for OAuth-only users
    name = Column(String(255), nullable=False)
    avatar_url = Column(String(500))
    github_id = Column(String(100), unique=True, nullable=True, index=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), default=_utcnow)
    updated_at = Column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)

    team_memberships = relationship("TeamMember", back_populates="user")
    api_keys = relationship("APIKeyModel", back_populates="user")


class Team(Base):
    __tablename__ = "teams"

    id = Column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    org_id = Column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    name = Column(String(255), nullable=False)
    slug = Column(String(255), nullable=False)
    created_at = Column(DateTime(timezone=True), default=_utcnow)

    organization = relationship("Organization", back_populates="teams")
    members = relationship(
        "TeamMember", back_populates="team", cascade="all, delete-orphan"
    )
    projects = relationship(
        "Project", back_populates="team", cascade="all, delete-orphan"
    )

    __table_args__ = (UniqueConstraint("org_id", "slug", name="uq_team_org_slug"),)


class TeamMember(Base):
    __tablename__ = "team_members"

    id = Column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    team_id = Column(
        UUID(as_uuid=True), ForeignKey("teams.id", ondelete="CASCADE"), nullable=False
    )
    user_id = Column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    role = Column(String(50), default="member")  # owner | admin | member | viewer
    joined_at = Column(DateTime(timezone=True), default=_utcnow)

    team = relationship("Team", back_populates="members")
    user = relationship("User", back_populates="team_memberships")

    __table_args__ = (UniqueConstraint("team_id", "user_id", name="uq_team_member"),)


# ═══════════════════════════════════════════════════════════════════════
# Projects & Scans
# ═══════════════════════════════════════════════════════════════════════


class Project(Base):
    __tablename__ = "projects"

    id = Column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    team_id = Column(
        UUID(as_uuid=True), ForeignKey("teams.id", ondelete="CASCADE"), nullable=False
    )
    name = Column(String(255), nullable=False)
    repo_url = Column(String(500), nullable=False)
    default_branch = Column(String(100), default="main")
    settings = Column(JSONB, default=dict)
    created_at = Column(DateTime(timezone=True), default=_utcnow)
    updated_at = Column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)

    team = relationship("Team", back_populates="projects")
    scans = relationship("Scan", back_populates="project", cascade="all, delete-orphan")


class Scan(Base):
    __tablename__ = "scans"

    id = Column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    project_id = Column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=True
    )
    triggered_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    branch = Column(String(100), default="main")
    status = Column(
        String(50), default="pending"
    )  # pending | processing | completed | failed
    scan_type = Column(String(20), default="repo")  # repo | pr
    pr_number = Column(Integer, nullable=True)
    debt_score = Column(Integer, nullable=True)
    commit_sha = Column(String(40), nullable=True)  # HEAD sha at time of scan
    summary = Column(JSONB, default=dict)
    detection_results = Column(JSONB, default=dict)
    ranked_issues = Column(JSONB, default=list)
    fix_proposals = Column(JSONB, default=list)
    hotspots = Column(JSONB, default=list)
    tdr = Column(JSONB, default=dict)
    duration_seconds = Column(Float, nullable=True)
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=_utcnow)

    project = relationship("Project", back_populates="scans")
    issues = relationship(
        "ScanIssue", back_populates="scan", cascade="all, delete-orphan"
    )
    ai_jobs = relationship("AIJob", back_populates="scan", cascade="all, delete-orphan")
    pull_requests = relationship(
        "PullRequest", back_populates="scan", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("ix_scan_project_status", "project_id", "status"),
        Index("ix_scan_created", "created_at"),
        UniqueConstraint("project_id", "pr_number", name="uq_project_pr"),
    )


class ScanIssue(Base):
    __tablename__ = "scan_issues"

    id = Column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    scan_id = Column(
        UUID(as_uuid=True), ForeignKey("scans.id", ondelete="CASCADE"), nullable=False
    )
    type = Column(String(100), nullable=False)
    severity = Column(String(20), nullable=False)  # CRITICAL | HIGH | MEDIUM | LOW
    file_path = Column(String(500))
    line_start = Column(Integer)
    line_end = Column(Integer)
    description = Column(Text)
    category = Column(String(100))
    confidence = Column(Float, default=0.9)
    cost_usd = Column(Float, default=0.0)
    score = Column(Integer)
    priority = Column(String(20))
    created_at = Column(DateTime(timezone=True), default=_utcnow)

    scan = relationship("Scan", back_populates="issues")

    __table_args__ = (Index("ix_issue_scan_severity", "scan_id", "severity"),)


class FixProposalModel(Base):
    __tablename__ = "fix_proposals"

    id = Column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    scan_id = Column(
        UUID(as_uuid=True), ForeignKey("scans.id", ondelete="CASCADE"), nullable=False
    )
    issue_id = Column(UUID(as_uuid=True), ForeignKey("scan_issues.id"), nullable=True)
    issue_type = Column(String(100))
    problem_summary = Column(Text)
    fix_summary = Column(Text)
    before_code = Column(Text, default="")
    after_code = Column(Text, default="")
    steps = Column(JSONB, default=list)
    source = Column(String(50), default="ai")  # ai | template | fallback
    created_at = Column(DateTime(timezone=True), default=_utcnow)


class PullRequest(Base):
    __tablename__ = "pull_requests"

    id = Column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    scan_id = Column(
        UUID(as_uuid=True), ForeignKey("scans.id", ondelete="CASCADE"), nullable=False
    )
    pr_number = Column(Integer)
    title = Column(String(500))
    html_url = Column(String(500))
    branch_name = Column(String(255))
    status = Column(String(50), default="open")  # open | merged | closed
    created_at = Column(DateTime(timezone=True), default=_utcnow)

    scan = relationship("Scan", back_populates="pull_requests")


# ═══════════════════════════════════════════════════════════════════════
# AI Jobs & Embeddings
# ═══════════════════════════════════════════════════════════════════════


class AIJob(Base):
    __tablename__ = "ai_jobs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    scan_id = Column(
        UUID(as_uuid=True), ForeignKey("scans.id", ondelete="CASCADE"), nullable=True
    )
    job_type = Column(String(50))  # analysis | embedding | fix_generation | pr_creation
    status = Column(
        String(50), default="queued"
    )  # queued | processing | completed | failed
    model_used = Column(String(100))
    tokens_input = Column(Integer, default=0)
    tokens_output = Column(Integer, default=0)
    latency_ms = Column(Float, default=0)
    result = Column(JSONB, default=dict)
    error = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=_utcnow)
    completed_at = Column(DateTime(timezone=True), nullable=True)

    scan = relationship("Scan", back_populates="ai_jobs")


class CodeEmbedding(Base):
    __tablename__ = "code_embeddings"

    id = Column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    project_id = Column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
    )
    file_path = Column(String(500))
    chunk_start = Column(Integer)
    chunk_end = Column(Integer)
    content = Column(Text)
    embedding = Column(Vector(1536))
    created_at = Column(DateTime(timezone=True), default=_utcnow)

    __table_args__ = (
        Index("ix_code_embeddings_project", "project_id"),
        Index(
            "ix_code_embeddings_embedding",
            "embedding",
            postgresql_using="hnsw",
            postgresql_with={"m": 16, "ef_construction": 64},
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
    )


# ═══════════════════════════════════════════════════════════════════════
# Billing & Subscriptions
# ═══════════════════════════════════════════════════════════════════════


class Subscription(Base):
    __tablename__ = "subscriptions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    org_id = Column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    stripe_customer_id = Column(String(255), nullable=True)
    stripe_subscription_id = Column(String(255), nullable=True)
    plan = Column(String(50), default="free")
    status = Column(String(50), default="active")  # active | past_due | canceled
    scans_limit_monthly = Column(Integer, default=5)
    scans_used = Column(Integer, default=0)
    current_period_end = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=_utcnow)

    organization = relationship("Organization", back_populates="subscriptions")


# ═══════════════════════════════════════════════════════════════════════
# API Keys, Usage, Webhooks
# ═══════════════════════════════════════════════════════════════════════


class APIKeyModel(Base):
    __tablename__ = "api_keys"

    id = Column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    org_id = Column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id = Column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    key_prefix = Column(String(20), nullable=False)
    key_hash = Column(String(255), nullable=False, unique=True)
    label = Column(String(255), default="default")
    is_active = Column(Boolean, default=True)
    last_used_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=_utcnow)

    organization = relationship("Organization", back_populates="api_keys")
    user = relationship("User", back_populates="api_keys")


class UsageLog(Base):
    __tablename__ = "usage_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    org_id = Column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    action = Column(String(100), nullable=False)
    metadata_ = Column("metadata", JSONB, default=dict)
    created_at = Column(DateTime(timezone=True), default=_utcnow)

    organization = relationship("Organization", back_populates="usage_logs")


class Webhook(Base):
    __tablename__ = "webhooks"

    id = Column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    org_id = Column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    url = Column(String(500), nullable=False)
    secret_hash = Column(String(255))
    events = Column(JSONB, default=list)  # ["scan.completed", "fix.created", ...]
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), default=_utcnow)

    organization = relationship("Organization", back_populates="webhooks")


class GitHubInstallation(Base):
    __tablename__ = "github_installations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    org_id = Column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    installation_id = Column(Integer, unique=True, nullable=False, index=True)
    account_login = Column(String(255), nullable=False)  # GitHub user/org login
    account_type = Column(String(50), default="User")  # User | Organization
    access_token = Column(String(500), nullable=True)  # cached token (ephemeral)
    token_expires_at = Column(DateTime(timezone=True), nullable=True)
    repos_synced_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=_utcnow)

    organization = relationship("Organization", back_populates="github_installations")
