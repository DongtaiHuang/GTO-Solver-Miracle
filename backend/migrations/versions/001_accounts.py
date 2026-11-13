"""Account identities, revocable logins and private study records."""

from alembic import op

revision = "001_accounts"
down_revision = None


def upgrade():
    op.execute("""
    CREATE TABLE members (
        id uuid PRIMARY KEY, issuer text NOT NULL, subject text NOT NULL,
        display_name text NOT NULL, verified_email text,
        created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now(),
        UNIQUE (issuer, subject)
    );
    CREATE TABLE logins (
        digest text PRIMARY KEY, owner uuid NOT NULL REFERENCES members ON DELETE CASCADE,
        expires timestamptz NOT NULL
    );
    CREATE INDEX logins_expiry ON logins(expires);
    CREATE INDEX logins_owner ON logins(owner);
    CREATE TABLE challenges (
        digest text PRIMARY KEY, nonce text NOT NULL, expires timestamptz NOT NULL
    );
    CREATE INDEX challenge_expiry ON challenges(expires);
    CREATE TABLE saved_hands (
        owner uuid NOT NULL REFERENCES members ON DELETE CASCADE, id uuid NOT NULL,
        title varchar(100) NOT NULL, hand jsonb NOT NULL, source text NOT NULL,
        source_id text, version text NOT NULL,
        created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now(),
        PRIMARY KEY(owner,id)
    );
    CREATE TABLE opponent_archives (
        owner uuid PRIMARY KEY REFERENCES members ON DELETE CASCADE, archive jsonb NOT NULL,
        revision integer NOT NULL CHECK(revision > 0), updated_at timestamptz NOT NULL DEFAULT now()
    );
    CREATE TABLE practice_sessions (
        owner uuid NOT NULL REFERENCES members ON DELETE CASCADE, id uuid NOT NULL,
        PRIMARY KEY(owner,id)
    );
    CREATE TABLE practice_attempts (
        owner uuid NOT NULL, id uuid NOT NULL, session uuid NOT NULL, attempt jsonb NOT NULL,
        PRIMARY KEY(owner,id), FOREIGN KEY(owner,session) REFERENCES practice_sessions ON DELETE CASCADE
    );
    CREATE INDEX practice_attempts_session ON practice_attempts(owner,session);
    """)


def downgrade():
    raise RuntimeError("Restore a separately verified backup to roll back this initial schema")
