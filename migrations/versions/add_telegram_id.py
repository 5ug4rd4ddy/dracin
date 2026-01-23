from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'add_telegram_id'
down_revision = '5f2a66543566'
branch_labels = None
depends_on = None

def upgrade():
    op.add_column('users', sa.Column('telegram_id', sa.String(length=50), nullable=True))
    op.create_unique_constraint('uq_users_telegram_id', 'users', ['telegram_id'])

def downgrade():
    op.drop_constraint('uq_users_telegram_id', 'users', type_='unique')
    op.drop_column('users', 'telegram_id')
