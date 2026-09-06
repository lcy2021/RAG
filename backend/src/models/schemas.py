"""HTTP DTOs for settings, pipelines, knowledge bases, scenarios, and chat."""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator

from models.enums import CredentialKind, PipelineKind, PipelineStage, SlotMode
from plugins.define import FORBIDDEN_PARAM_KEYS


class HealthResponse(BaseModel):
    status: str = "ok"
    version: str
    database: str = "skipped"


class PluginSummary(BaseModel):
    stage: PipelineStage
    name: str
    version: str
    description: str = ""
    source: str = "builtin"
    config_schema: dict = Field(default_factory=dict)
    default_params: dict = Field(default_factory=dict)
    is_enabled: bool = True


def _reject_secret_params(params: dict[str, Any]) -> dict[str, Any]:
    lowered = {str(key).lower() for key in params}
    overlap = lowered & FORBIDDEN_PARAM_KEYS
    if overlap:
        raise ValueError(f"params must not contain secret keys: {sorted(overlap)}")
    return params


class CredentialCreate(BaseModel):
    name: str
    kind: CredentialKind
    model_name: str
    secret: str = Field(description="Pasted key; stored at rest, never returned in list APIs")
    provider: str = "openai"
    base_url: str | None = None
    extra: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def secret_present(self) -> "CredentialCreate":
        if not (self.secret or "").strip():
            raise ValueError("secret is required")
        return self


class CredentialUpdate(BaseModel):
    """Partial update. Omit secret (or leave blank) to keep the stored key."""

    name: str | None = None
    kind: CredentialKind | None = None
    model_name: str | None = None
    secret: str | None = Field(
        default=None,
        description="New key; omit or blank to keep the existing secret",
    )
    provider: str | None = None
    base_url: str | None = None
    extra: dict[str, Any] | None = None


class CredentialOut(BaseModel):
    id: UUID
    name: str
    kind: CredentialKind
    provider: str
    plugin_name: str
    model_name: str
    base_url: str | None
    key_hint: str | None
    extra: dict[str, Any]
    created_at: datetime
    updated_at: datetime


class SlotBindingIn(BaseModel):
    name: str
    params: dict[str, Any] = Field(default_factory=dict)

    @field_validator("params")
    @classmethod
    def no_secrets(cls, value: dict[str, Any]) -> dict[str, Any]:
        return _reject_secret_params(value)


class PipelineSlotIn(BaseModel):
    stage: PipelineStage
    mode: SlotMode = SlotMode.FIRST
    ordinal: int | None = None
    bindings: list[SlotBindingIn]

    @model_validator(mode="after")
    def bindings_ok(self) -> "PipelineSlotIn":
        if not self.bindings:
            raise ValueError("bindings must be non-empty")
        if self.mode == SlotMode.FIRST and len(self.bindings) != 1:
            raise ValueError("mode=first requires exactly one binding")
        return self


class PipelineCreate(BaseModel):
    name: str
    kind: PipelineKind
    description: str | None = None
    definition: dict[str, Any] = Field(default_factory=dict)
    slots: list[PipelineSlotIn]


class PipelineUpdate(BaseModel):
    """Replace name, description, definition, and slots; kind is immutable."""

    name: str
    description: str | None = None
    definition: dict[str, Any] = Field(default_factory=dict)
    slots: list[PipelineSlotIn]


class PipelineSlotOut(BaseModel):
    id: UUID
    stage: PipelineStage
    mode: SlotMode
    ordinal: int
    bindings: list[dict[str, Any]]


class PipelineOut(BaseModel):
    id: UUID
    name: str
    kind: PipelineKind
    description: str | None
    definition: dict[str, Any]
    slots: list[PipelineSlotOut]
    created_at: datetime
    updated_at: datetime


class KnowledgeBaseCreate(BaseModel):
    name: str
    description: str | None = None
    ingest_pipeline_id: UUID


class VectorCollectionOut(BaseModel):
    id: UUID
    name: str
    embedder_binding_id: UUID
    metric: str
    dim: int | None
    is_default: bool


class KnowledgeBaseOut(BaseModel):
    id: UUID
    name: str
    description: str | None
    ingest_pipeline_id: UUID | None
    query_pipeline_id: UUID | None
    default_embedder_binding_id: UUID | None
    default_generator_binding_id: UUID | None
    collections: list[VectorCollectionOut] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class DocumentOut(BaseModel):
    id: UUID
    knowledge_base_id: UUID
    source_uri: str
    title: str | None
    status: str
    content_hash: str
    created_at: datetime


class IngestJobOut(BaseModel):
    id: UUID
    knowledge_base_id: UUID
    document_id: UUID | None
    status: str
    error_message: str | None
    stats: dict[str, Any]
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None


class ConversationCreate(BaseModel):
    knowledge_base_id: UUID
    pipeline_config_id: UUID
    title: str | None = None
    history_window: int = 10


class ConversationOut(BaseModel):
    id: UUID
    knowledge_base_id: UUID | None
    pipeline_config_id: UUID | None
    title: str | None
    history_window: int
    created_at: datetime
    updated_at: datetime


class ChatMessageIn(BaseModel):
    content: str


class ChatMessageOut(BaseModel):
    id: UUID
    conversation_id: UUID
    turn_index: int
    role: str
    content: str
    rag_run_id: UUID | None
    created_at: datetime


class RetrievedSourceOut(BaseModel):
    rank: int
    chunk_id: UUID | None = None
    content: str
    score: float | None = None
    retriever: str = "dense"
    cited: bool = False


class CitationOut(BaseModel):
    rank: int
    char_start: int | None = None
    char_end: int | None = None
    quote: str | None = None


class StageTraceOut(BaseModel):
    stage: str
    plugin_name: str
    ordinal: int = 0
    latency_ms: int | None = None
    output: dict[str, Any] | None = None
    error_message: str | None = None


class ChatTurnOut(BaseModel):
    conversation_id: UUID
    user: ChatMessageOut
    assistant: ChatMessageOut
    rag_run_id: UUID
    traces: list[StageTraceOut] = Field(default_factory=list)
    sources: list[RetrievedSourceOut] = Field(default_factory=list)
    citations: list[CitationOut] = Field(default_factory=list)


class RagRunSourcesOut(BaseModel):
    rag_run_id: UUID
    sources: list[RetrievedSourceOut] = Field(default_factory=list)
    citations: list[CitationOut] = Field(default_factory=list)
    traces: list[StageTraceOut] = Field(default_factory=list)


class EvalItemSpanCreate(BaseModel):
    document_id: UUID
    quote: str
    char_start: int | None = None
    char_end: int | None = None


class EvalItemSpanOut(BaseModel):
    id: UUID
    eval_item_id: UUID
    document_id: UUID
    char_start: int | None
    char_end: int | None
    quote: str


class EvalItemCreate(BaseModel):
    question: str
    expected: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class EvalItemUpdate(BaseModel):
    question: str
    expected: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class EvalItemOut(BaseModel):
    id: UUID
    dataset_id: UUID
    question: str
    expected: str | None
    metadata: dict[str, Any]
    spans: list[EvalItemSpanOut] = Field(default_factory=list)


class ScenarioCreate(BaseModel):
    name: str
    knowledge_base_id: UUID
    metric_plugins: list[str] = Field(min_length=1)
    metric_weights: dict[str, float] = Field(default_factory=dict)
    latency_p95_ms_max: int | None = None
    cost_micros_max: int | None = None
    notes: str | None = None


class ScenarioUpdate(BaseModel):
    """Replace name, metrics, weights, SLOs, and notes; KB and dataset are immutable."""

    name: str
    metric_plugins: list[str] = Field(min_length=1)
    metric_weights: dict[str, float] = Field(default_factory=dict)
    latency_p95_ms_max: int | None = None
    cost_micros_max: int | None = None
    notes: str | None = None


class ScenarioOut(BaseModel):
    id: UUID
    name: str
    knowledge_base_id: UUID
    dataset_id: UUID
    metric_plugins: list[str]
    metric_weights: dict[str, Any]
    latency_p95_ms_max: int | None
    cost_micros_max: int | None
    notes: str | None
    item_count: int = 0
    created_at: datetime


class ScenarioDetailOut(ScenarioOut):
    items: list[EvalItemOut] = Field(default_factory=list)


class EvalItemImportSpan(BaseModel):
    """Span for import. Prefer document_id; otherwise match document by title or source_uri."""

    quote: str
    document_id: UUID | None = None
    document: str | None = None
    char_start: int | None = None
    char_end: int | None = None


class EvalItemImportRow(BaseModel):
    question: str
    expected: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    spans: list[EvalItemImportSpan] = Field(default_factory=list)


class ScenarioItemsImport(BaseModel):
    items: list[EvalItemImportRow] = Field(min_length=1)
    replace: bool = False


class ScenarioItemsImportResult(BaseModel):
    created_items: int
    created_spans: int
    replaced: bool
    warnings: list[str] = Field(default_factory=list)


class SlotOverrideIn(BaseModel):
    plugin: str
    params: dict[str, Any] = Field(default_factory=dict)

    @field_validator("params")
    @classmethod
    def no_secrets(cls, value: dict[str, Any]) -> dict[str, Any]:
        return _reject_secret_params(value)


class CompareVariantIn(BaseModel):
    label: str
    query_pipeline_id: UUID | None = None
    vector_collection_id: UUID | None = None
    slot_overrides: dict[str, SlotOverrideIn] = Field(default_factory=dict)


class ExperimentCreate(BaseModel):
    name: str
    scenario_id: UUID
    query_pipeline_id: UUID
    variants: list[CompareVariantIn] = Field(min_length=2)
    metric_plugins: list[str] | None = None
    judge_binding_id: UUID | None = None
    notes: str | None = None


class ExperimentOut(BaseModel):
    id: UUID
    name: str
    scenario_id: UUID
    compare_spec_id: UUID
    judge_binding_id: UUID | None
    metric_plugins: list[str]
    scenario_name: str | None = None
    compare_spec_name: str | None = None
    run_count: int = 0
    created_at: datetime


class EvalRunOut(BaseModel):
    id: UUID
    experiment_id: UUID
    status: str
    corpus_fingerprint: str | None
    snapshot: dict[str, Any]
    winner_variant_id: UUID | None
    error_message: str | None
    created_at: datetime
    finished_at: datetime | None


class EvalScoreOut(BaseModel):
    id: UUID
    eval_run_id: UUID
    eval_item_id: UUID
    compare_variant_id: UUID
    rag_run_id: UUID | None
    metric: str
    value: float
    detail: dict[str, Any]


class EvalSummaryOut(BaseModel):
    id: UUID
    eval_run_id: UUID
    compare_variant_id: UUID
    metrics: dict[str, Any]
    composite_score: float | None
    latency_p50_ms: int | None
    latency_p95_ms: int | None
    cost_micros_avg: int | None
    rank: int | None
    is_winner: bool


class EvalVariantProgressOut(BaseModel):
    id: UUID
    label: str
    ordinal: int = 0
    query_pipeline_id: UUID | None = None
    query_pipeline_name: str | None = None
    status: str = "queued"
    done_items: int = 0
    total_items: int = 0
    error_message: str | None = None


class EvalRunDetailOut(EvalRunOut):
    summaries: list[EvalSummaryOut] = Field(default_factory=list)
    scores: list[EvalScoreOut] = Field(default_factory=list)
    variants: list[EvalVariantProgressOut] = Field(default_factory=list)


class PromoteRequest(BaseModel):
    compare_variant_id: UUID | None = None


class PromotionOut(BaseModel):
    id: UUID
    scenario_id: UUID
    eval_run_id: UUID
    compare_variant_id: UUID
    knowledge_base_id: UUID
    ingest_pipeline_id: UUID | None
    query_pipeline_id: UUID | None
    vector_collection_id: UUID | None
    variant_label: str | None = None
    query_pipeline_name: str | None = None
    created_at: datetime


class UsageBucketOut(BaseModel):
    run_count: int = 0
    token_in: int = 0
    token_out: int = 0
    token_cached: int = 0
    cost_micros: int | None = None


class UsageSummaryOut(BaseModel):
    total: UsageBucketOut
    chat: UsageBucketOut
    experiment: UsageBucketOut


class ConversationUsageOut(BaseModel):
    conversation_id: UUID
    title: str | None
    knowledge_base_id: UUID | None
    pipeline_config_id: UUID | None
    updated_at: datetime
    run_count: int
    token_in: int
    token_out: int
    token_cached: int
    cost_micros: int | None
    last_run_at: datetime | None


class ExperimentUsageOut(BaseModel):
    experiment_id: UUID
    experiment_name: str
    eval_run_count: int
    run_count: int
    token_in: int
    token_out: int
    token_cached: int
    cost_micros: int | None
    last_run_at: datetime | None
