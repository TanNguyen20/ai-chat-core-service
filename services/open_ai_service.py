import time
from typing import Iterable

from openai import OpenAI

from services import MODEL_NAME, API_KEY, BASE_URL
from utils.common import sse, heartbeat

client = OpenAI(
    base_url=BASE_URL,
    api_key=API_KEY,
)


class OpenAIService:
    @staticmethod
    def sumary_files():
        response = client.responses.create(
            model=MODEL_NAME,
            input=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "input_text",
                            "text": "Analyze the letter and provide a summary of the key points.",
                        },
                        {
                            "type": "input_file",
                            "file_url": "https://www.berkshirehathaway.com/letters/2024ltr.pdf",
                        },
                    ],
                },
            ],
            stream=True
        )
        yield response.choices[0].message.content[0].text

    @staticmethod
    def ask_question_stream_response(prompt: str) -> Iterable[str]:
        """
        Yields SSE lines from OpenAI Chat Completions streaming.
        Event sequence: start -> (delta...)+ -> end  OR start -> error -> end
        """
        rid = f"resp_{int(time.time() * 1000)}"

        # 1) start
        yield sse("start", {"id": rid, "model": MODEL_NAME, "created": int(time.time())})

        last_heartbeat = time.time()
        try:
            stream = client.chat.completions.create(
                model=MODEL_NAME,
                messages=[
                    {"role": "system", "content": "You are a helpful assistant."},
                    {"role": "user", "content": prompt},
                ],
                stream=True,
            )

            for chunk in stream:
                # delta text lives here (may be None)
                delta = getattr(chunk.choices[0].delta, "content", None)
                if delta:
                    yield sse("delta", {"index": 0, "content": delta})

                # heartbeat every 15s to keep proxies happy
                if time.time() - last_heartbeat > 15:
                    yield heartbeat()
                    last_heartbeat = time.time()

            # 3) end
            yield sse("end", {"finish_reason": "stop"})

        except Exception as e:
            # 2) error -> end
            yield sse("error", {"message": str(e)})
            yield sse("end", {"finish_reason": "error"})
