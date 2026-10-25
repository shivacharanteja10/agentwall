"""Initial migration - create all tables.

Revision ID: 001_initial
Revises: 
Create Date: 2024-01-01 00:00:00.000000

"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

# revision identifiers, used by Alembic.
revision = '001_initial'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create agents table
    op.create_table(
        'agents',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('uuid', UUID(as_uuid=False), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('role', sa.Enum('admin', 'operator', 'viewer', 'automated', name='agentrole'), nullable=False, server_default='viewer'),
        sa.Column('api_key_hash', sa.String(255), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('last_seen_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('uuid'),
        sa.UniqueConstraint('name'),
    )
    op.create_index('ix_agents_uuid', 'agents', ['uuid'], unique=True)
    op.create_index('ix_agents_name', 'agents', ['name'], unique=True)

    # Create tool_servers table
    op.create_table(
        'tool_servers',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('base_url', sa.String(500), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name'),
    )
    op.create_index('ix_tool_servers_name', 'tool_servers', ['name'], unique=True)

    # Create tools table
    op.create_table(
        'tools',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('server_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('input_schema', JSONB(), nullable=False, server_default='{}'),
        sa.Column('output_schema', JSONB(), nullable=False, server_default='{}'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['server_id'], ['tool_servers.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_tools_server_id', 'tools', ['server_id'])
    op.create_index('ix_tools_name_active', 'tools', ['name', 'is_active'])
    op.create_unique_constraint('uq_tool_server_name', 'tools', ['server_id', 'name'])

    # Create policies table
    op.create_table(
        'policies',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('role', sa.Enum('admin', 'operator', 'viewer', 'automated', name='agentrole'), nullable=False),
        sa.Column('tool_name', sa.String(255), nullable=True),
        sa.Column('action', sa.String(50), nullable=False),
        sa.Column('argument_pattern', JSONB(), nullable=True),
        sa.Column('time_window_start', sa.String(5), nullable=True),
        sa.Column('time_window_end', sa.String(5), nullable=True),
        sa.Column('priority', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name'),
    )
    op.create_index('ix_policies_role_tool_active', 'policies', ['role', 'tool_name', 'is_active'])

    # Create tool_calls table
    op.create_table(
        'tool_calls',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('uuid', UUID(as_uuid=False), nullable=False),
        sa.Column('agent_id', sa.Integer(), nullable=True),
        sa.Column('tool_name', sa.String(255), nullable=False),
        sa.Column('arguments', JSONB(), nullable=False, server_default='{}'),
        sa.Column('result', JSONB(), nullable=True),
        sa.Column('status', sa.Enum('allowed', 'denied', 'pending_approval', 'approved', 'redacted', 'error', name='toolcallstatus'), nullable=False),
        sa.Column('policy_id', sa.Integer(), nullable=True),
        sa.Column('approval_id', sa.Integer(), nullable=True),
        sa.Column('threat_detected', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('threat_details', JSONB(), nullable=True),
        sa.Column('dlp_redacted', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('dlp_details', JSONB(), nullable=True),
        sa.Column('request_hash', sa.String(64), nullable=False),
        sa.Column('previous_hash', sa.String(64), nullable=True),
        sa.Column('chain_hash', sa.String(64), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['agent_id'], ['agents.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['policy_id'], ['policies.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('uuid'),
    )
    op.create_index('ix_tool_calls_uuid', 'tool_calls', ['uuid'], unique=True)
    op.create_index('ix_tool_calls_agent_created', 'tool_calls', ['agent_id', 'created_at'])
    op.create_index('ix_tool_calls_status_created', 'tool_calls', ['status', 'created_at'])
    op.create_index('ix_tool_calls_tool_name', 'tool_calls', ['tool_name'])

    # Create approval_requests table
    op.create_table(
        'approval_requests',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('uuid', UUID(as_uuid=False), nullable=False),
        sa.Column('tool_call_id', sa.Integer(), nullable=False),
        sa.Column('agent_id', sa.Integer(), nullable=True),
        sa.Column('tool_name', sa.String(255), nullable=False),
        sa.Column('arguments', JSONB(), nullable=False, server_default='{}'),
        sa.Column('reason', sa.Text(), nullable=False),
        sa.Column('status', sa.String(50), nullable=False, server_default='pending'),
        sa.Column('requested_by', sa.Integer(), nullable=True),
        sa.Column('decided_by', sa.Integer(), nullable=True),
        sa.Column('decision_reason', sa.Text(), nullable=True),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('decided_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['agent_id'], ['agents.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['decided_by'], ['agents.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['requested_by'], ['agents.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['tool_call_id'], ['tool_calls.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('uuid'),
        sa.UniqueConstraint('tool_call_id'),
    )
    op.create_index('ix_approval_requests_uuid', 'approval_requests', ['uuid'], unique=True)
    op.create_index('ix_approval_requests_status_expires', 'approval_requests', ['status', 'expires_at'])


def downgrade() -> None:
    op.drop_table('approval_requests')
    op.drop_table('tool_calls')
    op.drop_table('policies')
    op.drop_table('tools')
    op.drop_table('tool_servers')
    op.drop_table('agents')

    # Drop enum types
    op.execute('DROP TYPE IF EXISTS agentrole')
    op.execute('DROP TYPE IF EXISTS toolcallstatus')
