"""Shared enumerations. Values match PostgreSQL enums created by Alembic."""

from enum import StrEnum


class PipelineStage(StrEnum):
    LOADER = "loader"
    CHUNKER = "chunker"
    EMBEDDER = "embedder"
    INDEXER = "indexer"
    QUERY_TRANSFORMER = "query_transformer"
    RETRIEVER = "retriever"
    FUSION = "fusion"
    RERANKER = "reranker"
    GRADER = "grader"
    COMPRESSOR = "compressor"
    GENERATOR = "generator"
    EVALUATOR = "evaluator"


class PipelineKind(StrEnum):
    INGEST = "ingest"
    QUERY = "query"


class SlotMode(StrEnum):
    FIRST = "first"
    COMPARE = "compare"
    ENSEMBLE = "ensemble"


class SecretBackend(StrEnum):
    ENV = "env"
    ENCRYPTED = "encrypted"


class CredentialKind(StrEnum):
    VECTOR = "vector"
    LLM = "llm"


class ModelPurpose(StrEnum):
    EMBEDDER = "embedder"
    GENERATOR = "generator"
    RERANKER = "reranker"
    GRADER = "grader"


class DocumentStatus(StrEnum):
    PENDING = "pending"
    INDEXED = "indexed"
    FAILED = "failed"
    SUPERSEDED = "superseded"


class RunStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


class StorageBackend(StrEnum):
    LOCAL = "local"
    S3 = "s3"
