"""ORM entities. Table names and columns match the Alembic initial migration."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    Text,
    UniqueConstraint,
    Uuid,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, BYTEA, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db.base import Base
from db.types import pg_enum
from models.enums import (
    CredentialKind,
    DocumentStatus,
    PipelineKind,
    PipelineStage,
    RunStatus,
    SecretBackend,
    SlotMode,
    StorageBackend,
)

UUID_PK = Uuid(as_uuid=True)
TS = DateTime(timezone=True)


def _uuid() -> Mapped[UUID]:
    return mapped_column(UUID_PK, primary_key=True, server_default=text("gen_random_uuid()"))


def _created() -> Mapped[datetime]:
    return mapped_column(TS, nullable=False, server_default=text("now()"))


class Credential(Base):
    __tablename__ = "credentials"
    __table_args__ = (
        CheckConstraint(
            "(secret_backend = 'env' AND env_var_name IS NOT NULL) OR "
            "(secret_backend = 'encrypted' AND encrypted_payload IS NOT NULL)",
            name="credentials_secret_present",
        ),
    )

    id: Mapped[UUID] = _uuid()
    name: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    kind: Mapped[CredentialKind] = mapped_column(
        pg_enum(CredentialKind, "credential_kind"), nullable=False
    )
    provider: Mapped[str] = mapped_column(Text, nullable=False, default="openai")
    plugin_name: Mapped[str] = mapped_column(Text, nullable=False)
    model_name: Mapped[str] = mapped_column(Text, nullable=False)
    base_url: Mapped[str | None] = mapped_column(Text)
    secret_backend: Mapped[SecretBackend] = mapped_column(
        pg_enum(SecretBackend, "secret_backend"),
        nullable=False,
        default=SecretBackend.ENCRYPTED,
    )
    env_var_name: Mapped[str | None] = mapped_column(Text)
    encrypted_payload: Mapped[bytes | None] = mapped_column(BYTEA)
    key_hint: Mapped[str | None] = mapped_column(Text)
    extra: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    created_at: Mapped[datetime] = _created()
    updated_at: Mapped[datetime] = mapped_column(TS, nullable=False, server_default=text("now()"))


class PipelineConfig(Base):
    __tablename__ = "pipeline_configs"

    id: Mapped[UUID] = _uuid()
    name: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    kind: Mapped[PipelineKind] = mapped_column(
        pg_enum(PipelineKind, "pipeline_kind"), nullable=False
    )
    description: Mapped[str | None] = mapped_column(Text)
    definition: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    created_at: Mapped[datetime] = _created()
    updated_at: Mapped[datetime] = mapped_column(TS, nullable=False, server_default=text("now()"))
    slots: Mapped[list[PipelineSlot]] = relationship(
        back_populates="pipeline", cascade="all, delete-orphan", order_by="PipelineSlot.ordinal"
    )


class PipelineSlot(Base):
    __tablename__ = "pipeline_slots"
    __table_args__ = (
        UniqueConstraint(
            "pipeline_config_id", "stage", "ordinal", name="uq_pipeline_slots_stage_ord"
        ),
        CheckConstraint("jsonb_typeof(bindings) = 'array'", name="pipeline_slots_bindings_array"),
        CheckConstraint(
            "jsonb_array_length(bindings) >= 1", name="pipeline_slots_bindings_nonempty"
        ),
        CheckConstraint(
            "mode <> 'first' OR jsonb_array_length(bindings) = 1",
            name="pipeline_slots_first_one",
        ),
    )

    id: Mapped[UUID] = _uuid()
    pipeline_config_id: Mapped[UUID] = mapped_column(
        UUID_PK, ForeignKey("pipeline_configs.id", ondelete="CASCADE"), nullable=False
    )
    stage: Mapped[PipelineStage] = mapped_column(
        pg_enum(PipelineStage, "pipeline_stage"), nullable=False
    )
    mode: Mapped[SlotMode] = mapped_column(
        pg_enum(SlotMode, "slot_mode"), nullable=False, default=SlotMode.FIRST
    )
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False)
    bindings: Mapped[list[Any]] = mapped_column(
        JSONB, nullable=False, server_default=text("'[]'::jsonb")
    )
    pipeline: Mapped[PipelineConfig] = relationship(back_populates="slots")


class PluginRow(Base):
    __tablename__ = "plugins"
    __table_args__ = (
        UniqueConstraint("stage", "name", "version", name="uq_plugins_stage_name_version"),
    )

    id: Mapped[UUID] = _uuid()
    stage: Mapped[PipelineStage] = mapped_column(
        pg_enum(PipelineStage, "pipeline_stage"), nullable=False
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    version: Mapped[str] = mapped_column(Text, nullable=False, default="1.0.0")
    description: Mapped[str] = mapped_column(
        Text, nullable=False, default="", server_default=text("''")
    )
    config_schema: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text(r"""'{"type":"object","additionalProperties"\:false}'::jsonb"""),
    )
    default_params: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    source: Mapped[str] = mapped_column(Text, nullable=False, default="builtin")
    entry_point: Mapped[str | None] = mapped_column(Text)
    origin_path: Mapped[str | None] = mapped_column(Text)
    is_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class KnowledgeBase(Base):
    __tablename__ = "knowledge_bases"

    id: Mapped[UUID] = _uuid()
    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    ingest_pipeline_id: Mapped[UUID | None] = mapped_column(
        UUID_PK,
        ForeignKey(
            "pipeline_configs.id", use_alter=True, name="knowledge_bases_ingest_pipeline_fk"
        ),
    )
    query_pipeline_id: Mapped[UUID | None] = mapped_column(
        UUID_PK,
        ForeignKey("pipeline_configs.id", use_alter=True, name="knowledge_bases_query_pipeline_fk"),
    )
    default_embedder_binding_id: Mapped[UUID | None] = mapped_column(
        UUID_PK, ForeignKey("credentials.id")
    )
    default_generator_binding_id: Mapped[UUID | None] = mapped_column(
        UUID_PK, ForeignKey("credentials.id")
    )
    promoted_from_eval_run_id: Mapped[UUID | None] = mapped_column(
        UUID_PK,
        ForeignKey(
            "eval_runs.id",
            use_alter=True,
            name="knowledge_bases_promoted_eval_fk",
            ondelete="SET NULL",
        ),
    )
    deleted_at: Mapped[datetime | None] = mapped_column(TS)
    created_at: Mapped[datetime] = _created()
    updated_at: Mapped[datetime] = mapped_column(TS, nullable=False, server_default=text("now()"))


class VectorCollection(Base):
    __tablename__ = "vector_collections"
    __table_args__ = (
        UniqueConstraint("knowledge_base_id", "name", name="uq_vector_collections_kb_name"),
    )

    id: Mapped[UUID] = _uuid()
    knowledge_base_id: Mapped[UUID] = mapped_column(
        UUID_PK, ForeignKey("knowledge_bases.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    embedder_binding_id: Mapped[UUID] = mapped_column(
        UUID_PK, ForeignKey("credentials.id"), nullable=False
    )
    metric: Mapped[str] = mapped_column(Text, nullable=False, default="cosine")
    dim: Mapped[int | None] = mapped_column(Integer)
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = _created()


class StoredFile(Base):
    __tablename__ = "stored_files"

    id: Mapped[UUID] = _uuid()
    original_filename: Mapped[str] = mapped_column(Text, nullable=False)
    content_type: Mapped[str | None] = mapped_column(Text)
    byte_size: Mapped[int | None] = mapped_column(Integer)
    content_hash: Mapped[str] = mapped_column(Text, nullable=False)
    storage_backend: Mapped[StorageBackend] = mapped_column(
        pg_enum(StorageBackend, "storage_backend"), nullable=False, default=StorageBackend.LOCAL
    )
    storage_key: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    created_at: Mapped[datetime] = _created()


class Document(Base):
    __tablename__ = "documents"
    __table_args__ = (
        UniqueConstraint("knowledge_base_id", "source_uri", name="uq_documents_kb_uri"),
        Index("documents_kb_status_idx", "knowledge_base_id", "status"),
    )

    id: Mapped[UUID] = _uuid()
    knowledge_base_id: Mapped[UUID] = mapped_column(
        UUID_PK, ForeignKey("knowledge_bases.id", ondelete="CASCADE"), nullable=False
    )
    stored_file_id: Mapped[UUID | None] = mapped_column(
        UUID_PK, ForeignKey("stored_files.id", ondelete="SET NULL")
    )
    source_uri: Mapped[str] = mapped_column(Text, nullable=False)
    mime_type: Mapped[str | None] = mapped_column(Text)
    title: Mapped[str | None] = mapped_column(Text)
    content_hash: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[DocumentStatus] = mapped_column(
        pg_enum(DocumentStatus, "document_status"), nullable=False, default=DocumentStatus.PENDING
    )
    extra_metadata: Mapped[dict[str, Any]] = mapped_column(
        "metadata", JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    created_at: Mapped[datetime] = _created()


class DocumentVersion(Base):
    __tablename__ = "document_versions"
    __table_args__ = (
        UniqueConstraint("document_id", "version_no", name="uq_document_versions_no"),
    )

    id: Mapped[UUID] = _uuid()
    document_id: Mapped[UUID] = mapped_column(
        UUID_PK, ForeignKey("documents.id", ondelete="CASCADE"), nullable=False
    )
    version_no: Mapped[int] = mapped_column(Integer, nullable=False)
    content_hash: Mapped[str] = mapped_column(Text, nullable=False)
    raw_text: Mapped[str | None] = mapped_column(Text)
    byte_size: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = _created()


class Chunk(Base):
    __tablename__ = "chunks"
    __table_args__ = (
        UniqueConstraint(
            "document_version_id", "chunker_plugin", "ordinal", name="uq_chunks_version_plugin_ord"
        ),
        Index("chunks_parent_idx", "parent_chunk_id"),
        Index(
            "chunks_active_idx",
            "document_version_id",
            postgresql_where=text("superseded_at IS NULL"),
        ),
    )

    id: Mapped[UUID] = _uuid()
    document_version_id: Mapped[UUID] = mapped_column(
        UUID_PK, ForeignKey("document_versions.id", ondelete="CASCADE"), nullable=False
    )
    parent_chunk_id: Mapped[UUID | None] = mapped_column(
        UUID_PK, ForeignKey("chunks.id", ondelete="SET NULL")
    )
    chunker_plugin: Mapped[str] = mapped_column(Text, nullable=False)
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    token_count: Mapped[int | None] = mapped_column(Integer)
    extra_metadata: Mapped[dict[str, Any]] = mapped_column(
        "metadata", JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    superseded_at: Mapped[datetime | None] = mapped_column(TS)


class ChunkEmbedding(Base):
    __tablename__ = "chunk_embeddings"
    __table_args__ = (
        UniqueConstraint("chunk_id", "vector_collection_id", name="uq_chunk_embeddings_chunk_col"),
        Index("chunk_embeddings_collection_idx", "vector_collection_id"),
        CheckConstraint("vector_dims(embedding) = dim", name="chunk_embeddings_dim"),
    )

    id: Mapped[UUID] = _uuid()
    chunk_id: Mapped[UUID] = mapped_column(
        UUID_PK, ForeignKey("chunks.id", ondelete="CASCADE"), nullable=False
    )
    vector_collection_id: Mapped[UUID] = mapped_column(
        UUID_PK, ForeignKey("vector_collections.id", ondelete="CASCADE"), nullable=False
    )
    embedder_plugin: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[list[float]] = mapped_column(Vector(), nullable=False)
    dim: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = _created()


class IngestJob(Base):
    __tablename__ = "ingest_jobs"
    __table_args__ = (Index("ingest_jobs_kb_status_idx", "knowledge_base_id", "status"),)

    id: Mapped[UUID] = _uuid()
    knowledge_base_id: Mapped[UUID] = mapped_column(
        UUID_PK, ForeignKey("knowledge_bases.id", ondelete="CASCADE"), nullable=False
    )
    document_id: Mapped[UUID | None] = mapped_column(
        UUID_PK, ForeignKey("documents.id", ondelete="CASCADE")
    )
    document_version_id: Mapped[UUID | None] = mapped_column(
        UUID_PK, ForeignKey("document_versions.id", ondelete="SET NULL")
    )
    vector_collection_id: Mapped[UUID | None] = mapped_column(
        UUID_PK, ForeignKey("vector_collections.id")
    )
    ingest_pipeline_id: Mapped[UUID | None] = mapped_column(
        UUID_PK, ForeignKey("pipeline_configs.id", use_alter=True, name="ingest_jobs_pipeline_fk")
    )
    compare_variant_id: Mapped[UUID | None] = mapped_column(
        UUID_PK,
        ForeignKey(
            "compare_variants.id",
            use_alter=True,
            name="ingest_jobs_variant_fk",
            ondelete="SET NULL",
        ),
    )
    eval_run_id: Mapped[UUID | None] = mapped_column(
        UUID_PK,
        ForeignKey(
            "eval_runs.id", use_alter=True, name="ingest_jobs_eval_run_fk", ondelete="SET NULL"
        ),
    )
    status: Mapped[RunStatus] = mapped_column(
        pg_enum(RunStatus, "run_status"), nullable=False, default=RunStatus.QUEUED
    )
    error_message: Mapped[str | None] = mapped_column(Text)
    stats: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    created_at: Mapped[datetime] = _created()
    started_at: Mapped[datetime | None] = mapped_column(TS)
    finished_at: Mapped[datetime | None] = mapped_column(TS)


class IngestStageTrace(Base):
    __tablename__ = "ingest_stage_traces"

    id: Mapped[UUID] = _uuid()
    ingest_job_id: Mapped[UUID] = mapped_column(
        UUID_PK, ForeignKey("ingest_jobs.id", ondelete="CASCADE"), nullable=False
    )
    stage: Mapped[PipelineStage] = mapped_column(
        pg_enum(PipelineStage, "pipeline_stage"), nullable=False
    )
    plugin_name: Mapped[str] = mapped_column(Text, nullable=False)
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    output_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    error_message: Mapped[str | None] = mapped_column(Text)
    latency_ms: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = _created()


class CompareSpec(Base):
    __tablename__ = "compare_specs"

    id: Mapped[UUID] = _uuid()
    name: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    query_pipeline_id: Mapped[UUID] = mapped_column(
        UUID_PK, ForeignKey("pipeline_configs.id"), nullable=False
    )
    ingest_pipeline_id: Mapped[UUID | None] = mapped_column(
        UUID_PK, ForeignKey("pipeline_configs.id")
    )
    stage: Mapped[PipelineStage | None] = mapped_column(pg_enum(PipelineStage, "pipeline_stage"))
    definition: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    description: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = _created()


class CompareVariant(Base):
    __tablename__ = "compare_variants"
    __table_args__ = (
        UniqueConstraint("compare_spec_id", "label", name="uq_compare_variants_label"),
        UniqueConstraint("compare_spec_id", "ordinal", name="uq_compare_variants_ordinal"),
    )

    id: Mapped[UUID] = _uuid()
    compare_spec_id: Mapped[UUID] = mapped_column(
        UUID_PK, ForeignKey("compare_specs.id", ondelete="CASCADE"), nullable=False
    )
    label: Mapped[str] = mapped_column(Text, nullable=False)
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False)
    ingest_pipeline_id: Mapped[UUID | None] = mapped_column(
        UUID_PK, ForeignKey("pipeline_configs.id")
    )
    query_pipeline_id: Mapped[UUID | None] = mapped_column(
        UUID_PK, ForeignKey("pipeline_configs.id")
    )
    vector_collection_id: Mapped[UUID | None] = mapped_column(
        UUID_PK, ForeignKey("vector_collections.id")
    )
    slot_overrides: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )


class Conversation(Base):
    __tablename__ = "conversations"
    __table_args__ = (Index("conversations_updated_idx", "updated_at"),)

    id: Mapped[UUID] = _uuid()
    knowledge_base_id: Mapped[UUID | None] = mapped_column(
        UUID_PK, ForeignKey("knowledge_bases.id", ondelete="SET NULL")
    )
    pipeline_config_id: Mapped[UUID | None] = mapped_column(
        UUID_PK, ForeignKey("pipeline_configs.id")
    )
    title: Mapped[str | None] = mapped_column(Text)
    history_window: Mapped[int] = mapped_column(Integer, nullable=False, default=10)
    created_at: Mapped[datetime] = _created()
    updated_at: Mapped[datetime] = mapped_column(TS, nullable=False, server_default=text("now()"))


class Message(Base):
    __tablename__ = "messages"
    __table_args__ = (
        UniqueConstraint("conversation_id", "turn_index", "role", name="uq_messages_turn_role"),
        Index("messages_conversation_turn_idx", "conversation_id", "turn_index"),
    )

    id: Mapped[UUID] = _uuid()
    conversation_id: Mapped[UUID] = mapped_column(
        UUID_PK, ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False
    )
    turn_index: Mapped[int] = mapped_column(Integer, nullable=False)
    role: Mapped[str] = mapped_column(Text, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    rag_run_id: Mapped[UUID | None] = mapped_column(
        UUID_PK,
        ForeignKey("rag_runs.id", use_alter=True, name="messages_rag_run_fk", ondelete="SET NULL"),
    )
    token_count: Mapped[int | None] = mapped_column(Integer)
    extra_metadata: Mapped[dict[str, Any]] = mapped_column(
        "metadata", JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    created_at: Mapped[datetime] = _created()


class RagRun(Base):
    __tablename__ = "rag_runs"
    __table_args__ = (
        CheckConstraint(
            """
            (conversation_id IS NOT NULL AND trigger_message_id IS NOT NULL
             AND eval_run_id IS NULL AND eval_item_id IS NULL)
            OR
            (conversation_id IS NULL AND trigger_message_id IS NULL
             AND eval_run_id IS NOT NULL AND eval_item_id IS NOT NULL)
            """,
            name="rag_runs_online_or_eval",
        ),
        Index("rag_runs_message_idx", "trigger_message_id"),
        Index("rag_runs_conversation_idx", "conversation_id", "created_at"),
        Index("rag_runs_eval_idx", "eval_run_id", "eval_item_id"),
    )

    id: Mapped[UUID] = _uuid()
    conversation_id: Mapped[UUID | None] = mapped_column(
        UUID_PK, ForeignKey("conversations.id", ondelete="CASCADE")
    )
    trigger_message_id: Mapped[UUID | None] = mapped_column(
        UUID_PK, ForeignKey("messages.id", ondelete="CASCADE")
    )
    compare_variant_id: Mapped[UUID | None] = mapped_column(
        UUID_PK, ForeignKey("compare_variants.id", ondelete="SET NULL")
    )
    eval_run_id: Mapped[UUID | None] = mapped_column(
        UUID_PK,
        ForeignKey("eval_runs.id", use_alter=True, name="rag_runs_eval_run_fk", ondelete="CASCADE"),
    )
    eval_item_id: Mapped[UUID | None] = mapped_column(
        UUID_PK,
        ForeignKey(
            "eval_items.id", use_alter=True, name="rag_runs_eval_item_fk", ondelete="CASCADE"
        ),
    )
    pipeline_config_id: Mapped[UUID | None] = mapped_column(
        UUID_PK, ForeignKey("pipeline_configs.id")
    )
    knowledge_base_id: Mapped[UUID | None] = mapped_column(
        UUID_PK, ForeignKey("knowledge_bases.id", ondelete="SET NULL")
    )
    vector_collection_id: Mapped[UUID | None] = mapped_column(
        UUID_PK, ForeignKey("vector_collections.id", ondelete="SET NULL")
    )
    variant_label: Mapped[str] = mapped_column(Text, nullable=False, default="default")
    slot_overrides: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    resolved_params: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    status: Mapped[RunStatus] = mapped_column(
        pg_enum(RunStatus, "run_status"), nullable=False, default=RunStatus.QUEUED
    )
    rewritten_query: Mapped[str | None] = mapped_column(Text)
    answer_text: Mapped[str | None] = mapped_column(Text)
    error_message: Mapped[str | None] = mapped_column(Text)
    latency_ms: Mapped[int | None] = mapped_column(Integer)
    token_in: Mapped[int | None] = mapped_column(Integer)
    token_out: Mapped[int | None] = mapped_column(Integer)
    token_cached: Mapped[int | None] = mapped_column(Integer)
    cost_micros: Mapped[int | None] = mapped_column(BigInteger)
    created_at: Mapped[datetime] = _created()
    finished_at: Mapped[datetime | None] = mapped_column(TS)


class StageTrace(Base):
    __tablename__ = "stage_traces"
    __table_args__ = (Index("stage_traces_run_stage_idx", "rag_run_id", "stage", "ordinal"),)

    id: Mapped[UUID] = _uuid()
    rag_run_id: Mapped[UUID] = mapped_column(
        UUID_PK, ForeignKey("rag_runs.id", ondelete="CASCADE"), nullable=False
    )
    stage: Mapped[PipelineStage] = mapped_column(
        pg_enum(PipelineStage, "pipeline_stage"), nullable=False
    )
    plugin_name: Mapped[str] = mapped_column(Text, nullable=False)
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    input_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    output_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    score: Mapped[float | None] = mapped_column(Float)
    latency_ms: Mapped[int | None] = mapped_column(Integer)
    error_message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = _created()


class RetrievedChunk(Base):
    __tablename__ = "retrieved_chunks"
    __table_args__ = (
        UniqueConstraint("rag_run_id", "retriever", "rank", name="uq_retrieved_chunks"),
    )

    id: Mapped[UUID] = _uuid()
    rag_run_id: Mapped[UUID] = mapped_column(
        UUID_PK, ForeignKey("rag_runs.id", ondelete="CASCADE"), nullable=False
    )
    chunk_id: Mapped[UUID | None] = mapped_column(
        UUID_PK, ForeignKey("chunks.id", ondelete="SET NULL")
    )
    retriever: Mapped[str] = mapped_column(Text, nullable=False)
    rank: Mapped[int] = mapped_column(Integer, nullable=False)
    score: Mapped[float | None] = mapped_column(Float)
    fused_rank: Mapped[int | None] = mapped_column(Integer)
    content_snapshot: Mapped[str] = mapped_column(Text, nullable=False)
    extra_metadata: Mapped[dict[str, Any]] = mapped_column(
        "metadata", JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )


class Citation(Base):
    __tablename__ = "citations"

    id: Mapped[UUID] = _uuid()
    rag_run_id: Mapped[UUID] = mapped_column(
        UUID_PK, ForeignKey("rag_runs.id", ondelete="CASCADE"), nullable=False
    )
    retrieved_id: Mapped[UUID | None] = mapped_column(
        UUID_PK, ForeignKey("retrieved_chunks.id", ondelete="SET NULL")
    )
    char_start: Mapped[int | None] = mapped_column(Integer)
    char_end: Mapped[int | None] = mapped_column(Integer)
    quote: Mapped[str | None] = mapped_column(Text)


class EvalDataset(Base):
    __tablename__ = "eval_datasets"

    id: Mapped[UUID] = _uuid()
    knowledge_base_id: Mapped[UUID | None] = mapped_column(
        UUID_PK, ForeignKey("knowledge_bases.id", ondelete="SET NULL")
    )
    name: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    created_at: Mapped[datetime] = _created()


class EvalItem(Base):
    __tablename__ = "eval_items"

    id: Mapped[UUID] = _uuid()
    dataset_id: Mapped[UUID] = mapped_column(
        UUID_PK, ForeignKey("eval_datasets.id", ondelete="CASCADE"), nullable=False
    )
    question: Mapped[str] = mapped_column(Text, nullable=False)
    expected: Mapped[str | None] = mapped_column(Text)
    extra_metadata: Mapped[dict[str, Any]] = mapped_column(
        "metadata", JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )


class EvalItemSpan(Base):
    __tablename__ = "eval_item_spans"
    __table_args__ = (Index("eval_item_spans_item_idx", "eval_item_id"),)

    id: Mapped[UUID] = _uuid()
    eval_item_id: Mapped[UUID] = mapped_column(
        UUID_PK, ForeignKey("eval_items.id", ondelete="CASCADE"), nullable=False
    )
    document_id: Mapped[UUID] = mapped_column(
        UUID_PK, ForeignKey("documents.id", ondelete="CASCADE"), nullable=False
    )
    char_start: Mapped[int | None] = mapped_column(Integer)
    char_end: Mapped[int | None] = mapped_column(Integer)
    quote: Mapped[str] = mapped_column(Text, nullable=False)


class Scenario(Base):
    __tablename__ = "scenarios"
    __table_args__ = (
        CheckConstraint("cardinality(metric_plugins) >= 1", name="scenarios_metrics_nonempty"),
    )

    id: Mapped[UUID] = _uuid()
    name: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    knowledge_base_id: Mapped[UUID] = mapped_column(
        UUID_PK, ForeignKey("knowledge_bases.id"), nullable=False
    )
    dataset_id: Mapped[UUID] = mapped_column(
        UUID_PK, ForeignKey("eval_datasets.id"), nullable=False
    )
    metric_plugins: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False)
    metric_weights: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    latency_p95_ms_max: Mapped[int | None] = mapped_column(Integer)
    cost_micros_max: Mapped[int | None] = mapped_column(BigInteger)
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = _created()


class EvalExperiment(Base):
    __tablename__ = "eval_experiments"

    id: Mapped[UUID] = _uuid()
    name: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    scenario_id: Mapped[UUID] = mapped_column(UUID_PK, ForeignKey("scenarios.id"), nullable=False)
    compare_spec_id: Mapped[UUID] = mapped_column(
        UUID_PK, ForeignKey("compare_specs.id"), nullable=False
    )
    judge_binding_id: Mapped[UUID | None] = mapped_column(UUID_PK, ForeignKey("credentials.id"))
    metric_plugins: Mapped[list[str]] = mapped_column(
        ARRAY(Text), nullable=False, server_default=text("'{}'")
    )
    created_at: Mapped[datetime] = _created()


class EvalRun(Base):
    __tablename__ = "eval_runs"

    id: Mapped[UUID] = _uuid()
    experiment_id: Mapped[UUID] = mapped_column(
        UUID_PK, ForeignKey("eval_experiments.id", ondelete="CASCADE"), nullable=False
    )
    status: Mapped[RunStatus] = mapped_column(
        pg_enum(RunStatus, "run_status"), nullable=False, default=RunStatus.QUEUED
    )
    corpus_fingerprint: Mapped[str | None] = mapped_column(Text)
    snapshot: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    winner_variant_id: Mapped[UUID | None] = mapped_column(
        UUID_PK, ForeignKey("compare_variants.id")
    )
    error_message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = _created()
    finished_at: Mapped[datetime | None] = mapped_column(TS)


class EvalScore(Base):
    __tablename__ = "eval_scores"
    __table_args__ = (
        UniqueConstraint(
            "eval_run_id", "eval_item_id", "compare_variant_id", "metric", name="uq_eval_scores"
        ),
    )

    id: Mapped[UUID] = _uuid()
    eval_run_id: Mapped[UUID] = mapped_column(
        UUID_PK, ForeignKey("eval_runs.id", ondelete="CASCADE"), nullable=False
    )
    eval_item_id: Mapped[UUID] = mapped_column(
        UUID_PK, ForeignKey("eval_items.id", ondelete="CASCADE"), nullable=False
    )
    compare_variant_id: Mapped[UUID] = mapped_column(
        UUID_PK, ForeignKey("compare_variants.id"), nullable=False
    )
    rag_run_id: Mapped[UUID | None] = mapped_column(
        UUID_PK, ForeignKey("rag_runs.id", ondelete="SET NULL")
    )
    metric: Mapped[str] = mapped_column(Text, nullable=False)
    value: Mapped[float] = mapped_column(Float, nullable=False)
    detail: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )


class EvalSummary(Base):
    __tablename__ = "eval_summaries"
    __table_args__ = (
        UniqueConstraint("eval_run_id", "compare_variant_id", name="uq_eval_summaries"),
    )

    id: Mapped[UUID] = _uuid()
    eval_run_id: Mapped[UUID] = mapped_column(
        UUID_PK, ForeignKey("eval_runs.id", ondelete="CASCADE"), nullable=False
    )
    compare_variant_id: Mapped[UUID] = mapped_column(
        UUID_PK, ForeignKey("compare_variants.id"), nullable=False
    )
    metrics: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    composite_score: Mapped[float | None] = mapped_column(Float)
    latency_p50_ms: Mapped[int | None] = mapped_column(Integer)
    latency_p95_ms: Mapped[int | None] = mapped_column(Integer)
    cost_micros_avg: Mapped[int | None] = mapped_column(BigInteger)
    rank: Mapped[int | None] = mapped_column(Integer)
    is_winner: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class PipelinePromotion(Base):
    __tablename__ = "pipeline_promotions"

    id: Mapped[UUID] = _uuid()
    scenario_id: Mapped[UUID] = mapped_column(UUID_PK, ForeignKey("scenarios.id"), nullable=False)
    eval_run_id: Mapped[UUID] = mapped_column(UUID_PK, ForeignKey("eval_runs.id"), nullable=False)
    compare_variant_id: Mapped[UUID] = mapped_column(
        UUID_PK, ForeignKey("compare_variants.id"), nullable=False
    )
    knowledge_base_id: Mapped[UUID] = mapped_column(
        UUID_PK, ForeignKey("knowledge_bases.id"), nullable=False
    )
    ingest_pipeline_id: Mapped[UUID | None] = mapped_column(
        UUID_PK, ForeignKey("pipeline_configs.id")
    )
    query_pipeline_id: Mapped[UUID | None] = mapped_column(
        UUID_PK, ForeignKey("pipeline_configs.id")
    )
    vector_collection_id: Mapped[UUID | None] = mapped_column(
        UUID_PK, ForeignKey("vector_collections.id")
    )
    created_at: Mapped[datetime] = _created()
