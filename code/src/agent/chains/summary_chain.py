from langchain_core.prompts import ChatPromptTemplate
from agent.config import llm
from agent.prompts.summary import SUMMARY_PROMPT

summary_chain = ChatPromptTemplate.from_template(SUMMARY_PROMPT) | llm
