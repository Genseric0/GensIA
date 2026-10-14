"""Static agent metadata only; safe to import without loading execution tools."""
from dataclasses import asdict, dataclass
from typing import Literal


@dataclass(frozen=True)
class Capability:
    id: str
    dependencies: tuple[str, ...]
    model_use: Literal["none", "optional", "required"]
    limits: tuple[str, ...]


@dataclass(frozen=True)
class AgentInfo:
    id: str
    description: str
    capabilities: tuple[Capability, ...]


AGENTS = (
    AgentInfo("coordinator", "Valida a tarefa, delega e reúne estados; regras determinísticas.", (
        Capability("delegate", (), "none", ("Tarefas explícitas e sequenciais; sem worker permanente.",)),
    )),
    AgentInfo("security", "Inspeciona URLs passivamente e código Python com Bandit; sem LLM.", (
        Capability("analyze_url", (), "none", ("Não visita URLs nem verifica malware ou reputação.",)),
        Capability("scan_python", ("bandit",), "none", ("Requer workspace autorizado; não é sandbox do SO.",)),
    )),
    AgentInfo("reviewer", "Prioriza evidências da segurança e propõe revisão; Ollama opcional.", (
        Capability("review", ("ollama_if_model_requested",), "optional", (
            "Não aplica correções; recomendações do modelo exigem revisão humana.",)),
    )),
    AgentInfo("study", "Recupera documentos indicados e responde com fontes pelo Ollama local.", (
        Capability("answer_documents", ("ollama", "local_model", "pypdf_if_pdf"), "required", (
            "Apenas ficheiros explicitamente indicados e confinados ao workspace.",
            "Citações estruturais não comprovam a correção da resposta.",)),
    )),
)


@dataclass(frozen=True)
class CatalogSnapshot:
    schema_version: Literal[1]
    kind: Literal["static_capabilities"]
    runtime_state: Literal["not_observed"]
    execution_exposed: Literal[False]
    dependencies_checked: Literal[False]
    agents: tuple[AgentInfo, ...]


def catalog_snapshot():
    """Fresh JSON-compatible data, never an execution/readiness assertion."""
    return asdict(CatalogSnapshot(1, "static_capabilities", "not_observed", False, False, AGENTS))


def descriptions():
    """Keep the existing CLI list contract: id -> description."""
    return {agent.id: agent.description for agent in AGENTS}
