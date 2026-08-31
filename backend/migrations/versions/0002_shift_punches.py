"""Store editable IN and OUT punch pairs for each daily shift."""

from alembic import op
import sqlalchemy as sa


revision = "0002_shift_punches"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "shift_punches",
        sa.Column("shift_id", sa.String(length=36), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("in_time", sa.Time(), nullable=True),
        sa.Column("out_time", sa.Time(), nullable=True),
        sa.Column("confidence_score", sa.Integer(), nullable=False),
        sa.Column("verified", sa.Boolean(), nullable=False),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["shift_id"], ["shifts.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "shift_id",
            "sequence",
            name="uq_shift_punch_sequence",
        ),
    )


def downgrade() -> None:
    op.drop_table("shift_punches")
