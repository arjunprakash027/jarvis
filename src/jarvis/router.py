"""Router: Jev (TypeSafe) makes four judgments, a small table in code decides the route."""

from dataclasses import dataclass, field
import os

from typesafe_sdk import Choice, Noul, TypeSafeClient

from jarvis import router_questions as q
from jarvis.modules import REPO_ROOT, load_modules

ENV_FILE = REPO_ROOT / ".env"
YES, NO = 0.7, 0.3  # a Noul above YES is yes, below NO is no, between is unsettled


@dataclass(frozen=True)
class Judgments:
    """The four answers from Jev."""

    module_probs: dict[str, float]  # Choice: probability for each module
    fits: float  # Noul: some module can do this
    detail: float  # Noul: enough detail to start
    long: float  # Noul: more than about 10 steps

    def summary(self) -> str:
        probs = ", ".join(f"{k}: {v:.2f}" for k, v in sorted(self.module_probs.items(), key=lambda kv: kv[1], reverse=True))
        return f"probs: [{probs}] · fits: {self.fits:.2f} · detail: {self.detail:.2f} · long: {self.long:.2f}"


@dataclass(frozen=True)
class Route:
    """Either a module name, or a question for Arjun (kind is which, detail or no_fit)."""

    module: str | None = None
    kind: str | None = None
    question: str | None = None
    long_task: bool = False
    score: float = field(default=0.0, compare=False)  # top module probability, for the live log
    judgments: Judgments | None = field(default=None, compare=False)


def build_state(request: str, modules: dict[str, str]) -> dict:
    """State for Jev, built by code with no AI."""
    return {"request": request, "modules": modules}


def decide(j: Judgments) -> Route:
    """The decision table. First matching row wins."""
    ranked = sorted(j.module_probs.items(), key=lambda kv: kv[1], reverse=True)
    top, top_p = ranked[0]
    # No module fits: say so.
    if j.fits < NO:
        return Route(kind="no_fit", question=q.SAY_NO_FIT, judgments=j)
    # Fit unsettled, or the top module is not clearly ahead: ask which one.
    if j.fits < YES or top_p < YES:
        second = ranked[1][0] if len(ranked) > 1 else "something else"
        return Route(kind="which", question=q.ASK_WHICH.format(a=top, b=second), judgments=j)
    # Detail missing or unsettled: ask for it.
    if j.detail < YES:
        return Route(kind="detail", question=q.ASK_DETAIL, judgments=j)
    return Route(module=top, long_task=j.long >= YES, score=top_p, judgments=j)


def _api_key() -> str | None:
    """TYPESAFE_API_KEY from the environment, else from the one .env file."""
    key = os.environ.get("TYPESAFE_API_KEY")
    if key:
        return key
    if ENV_FILE.is_file():
        for line in ENV_FILE.read_text().splitlines():
            name, _, value = line.partition("=")
            if name.strip() == "TYPESAFE_API_KEY" and value.strip():
                return value.strip().strip("\"'")
    return None


def judge(request: str, modules: dict[str, str]) -> Judgments:
    """One request to Jev with the four questions. Errors raise; they are never an answer."""
    key = _api_key()
    if not key:
        raise RuntimeError("TYPESAFE_API_KEY is not set")
    with TypeSafeClient(api_key=key) as client:
        r = client.system_one(
            state=build_state(request, modules),
            questions={
                "module": Choice(instructions=q.WHICH_MODULE, criteria=dict(modules)),
                "fits": Noul(instructions=q.A_MODULE_FITS),
                "detail": Noul(
                    instructions=q.ENOUGH_DETAIL,
                    criteria={"true": q.ENOUGH_DETAIL_YES, "false": q.ENOUGH_DETAIL_NO},
                ),
                "long": Noul(instructions=q.LONG_TASK),
            },
        )
    return Judgments(
        module_probs=dict(r.choices["module"].probabilities),
        fits=r.nouls["fits"].noul,
        detail=r.nouls["detail"].noul,
        long=r.nouls["long"].noul,
    )


def route(request: str, modules: dict[str, str] | None = None) -> Route:
    """Route one request. Modules default to the ones in modules/."""
    if modules is None:
        modules = {m.name: m.description for m in load_modules()}
    return decide(judge(request, modules))
