from langsmith import traceable
from agent.config import llm, fallback_llm, llm_semaphore, record_tokens
from agent.prompts.review import REVIEW_PROMPT, REVIEW_FALLBACK_PROMPT
from agent.retriever import retrieve, format_context
from agent.knowledge_base.code_review_bp import CODE_REVIEW_BAD_PRACTICES
from agent.chains.models import parse_review_output
from agent.utils.logger import get_logger

log = get_logger(__name__)

_API_ERRORS = (ConnectionError, TimeoutError, OSError)


def _invoke(prompt, fallback):
    with llm_semaphore:
        try:
            result = llm.invoke(prompt)
        except _API_ERRORS as e:
            if fallback:
                log.warning("Primary LLM unavailable (%s), trying fallback", e)
                result = fallback.invoke(prompt)
            else:
                raise

    md = getattr(result, "response_metadata", {}) or {}
    usage = md.get("usage", {}) or {}
    prompt_tok = int(usage.get("prompt_tokens", 0) or 0)
    completion_tok = int(usage.get("completion_tokens", 0) or 0)
    record_tokens(prompt_tok, completion_tok)

    return result


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
