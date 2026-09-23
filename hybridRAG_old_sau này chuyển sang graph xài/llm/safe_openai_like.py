from llama_index.llms.openai_like import OpenAILike
from llama_index.core.base.llms.types import ChatResponse, ChatMessage, MessageRole


class SafeOpenAILike(OpenAILike):

    async def achat(self, messages, **kwargs):
        try:
            return await super().achat(messages, **kwargs)
        except (IndexError, TypeError) as e:
            msg = str(e)
            if "list index out of range" in msg or "NoneType" in msg or "subscriptable" in msg:
                print(f"[SAFE_LLM] Provider tra ve response bat thuong ({type(e).__name__}), "
                      f"dung placeholder thay vi crash")
                return ChatResponse(
                    message=ChatMessage(
                        role=MessageRole.ASSISTANT,
                        content="__EXTRACTION_FAILED__",
                    ),
                    raw={},
                )
            raise

    def chat(self, messages, **kwargs):
        try:
            return super().chat(messages, **kwargs)
        except (IndexError, TypeError) as e:
            msg = str(e)
            if "list index out of range" in msg or "NoneType" in msg or "subscriptable" in msg:
                print(f"[SAFE_LLM] Provider tra ve response bat thuong ({type(e).__name__}), "
                      f"dung placeholder thay vi crash")
                return ChatResponse(
                    message=ChatMessage(
                        role=MessageRole.ASSISTANT,
                        content="__EXTRACTION_FAILED__",
                    ),
                    raw={},
                )
            raise