from langsmith import traceable
from agent.config import llm, fallback_llm
from agent.prompts.review import REVIEW_PROMPT, REVIEW_FALLBACK_PROMPT
from agent.retriever import retrieve, format_context
from agent.knowledge_base.code_review_bp import CODE_REVIEW_BAD_PRACTICES
from agent.chains.models import parse_review_output
from agent.utils.logger import get_logger

log = get_logger(__name__)


def _invoke(prompt, fallback):
    try:
        return llm.invoke(prompt)
    except ConnectionError as e:
        if fallback:
            log.warning("Primary LLM unavailable, trying fallback")
            return fallback.invoke(prompt)
        raise


@traceable(name="review_chain", run_type="chain")
def review_chain(diff: str, diffs: list) -> str:
    entries = retrieve(diffs, CODE_REVIEW_BAD_PRACTICES, top_k=5)
    context = format_context(entries)
    prompt = REVIEW_PROMPT.format(diff=diff, context=context)
    result = _invoke(prompt, fallback_llm)

    if parse_review_output(result) is not None:
        return result

    log.warning("Review output failed validation, retrying with stricter prompt")
    fallback_prompt = REVIEW_FALLBACK_PROMPT.format(diff=diff, context=context)
    result2 = _invoke(fallback_prompt, fallback_llm)
    return result2
