from typing import Any

from .schemas import JEVAction, JEVDecision


class JEVDecisionEngine:
    """Decision boundary for the selected JEV implementation.

    Until the authoritative JEV paper/specification is configured, this provisional policy
    only maps observable memory state to safe actions and exposes that limitation to clients.
    """

    implementation = "provisional-memory-adequacy-policy"

    def decide_initial(self, *, memory_count: int, query: str) -> JEVDecision:
        if memory_count > 0:
            return JEVDecision(
                action=JEVAction.REUSE_OR_ACQUIRE,
                explanation="Existing scientific memory is available; reuse it and supplement only if evaluation finds gaps.",
                confidence=None,
                implementation=self.implementation,
            )
        return JEVDecision(
            action=JEVAction.ACQUIRE,
            explanation="No indexed scientific memory is available for this query, so external literature acquisition is required.",
            confidence=None,
            implementation=self.implementation,
        )

    def decide_after_evaluation(self, *, papers_found: int, evaluation_sufficient: bool) -> JEVDecision:
        if evaluation_sufficient:
            action = JEVAction.APPROVE
            explanation = "The workflow has sufficient evidence according to the supplied evaluation state."
        elif papers_found > 0:
            action = JEVAction.REFINE
            explanation = "Evidence was found but remains insufficient; a bounded refinement cycle is recommended."
        else:
            action = JEVAction.STOP_INSUFFICIENT_EVIDENCE
            explanation = "No usable papers were returned; stop transparently rather than fabricate an answer."
        return JEVDecision(
            action=action,
            explanation=explanation,
            confidence=None,
            implementation=self.implementation,
        )

