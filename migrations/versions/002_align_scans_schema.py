"""Align scans schema with ORM fields and nullable project linkage.

Revision ID: 002_align_scans_schema
Revises: 001_initial
Create Date: 2026-04-06
"""

from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "002_align_scans_schema"
down_revision: Union[str, None] = "001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column("scans", "project_id", existing_type=sa.UUID(), nullable=True)
    op.add_column("scans", sa.Column("scan_type", sa.String(length=20), nullable=True, server_default="repo"))
    op.add_column("scans", sa.Column("pr_number", sa.Integer(), nullable=True))
    op.add_column("scans", sa.Column("debt_score", sa.Integer(), nullable=True))
    op.add_column("scans", sa.Column("commit_sha", sa.String(length=40), nullable=True))
    op.create_unique_constraint("uq_project_pr", "scans", ["project_id", "pr_number"])


def downgrade() -> None:
    op.drop_constraint("uq_project_pr", "scans", type_="unique")
    op.drop_column("scans", "commit_sha")
    op.drop_column("scans", "debt_score")
    op.drop_column("scans", "pr_number")
    op.drop_column("scans", "scan_type")
    op.alter_column("scans", "project_id", existing_type=sa.UUID(), nullable=False)
