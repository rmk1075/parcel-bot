import time
from typing import TypedDict

from langgraph.config import get_stream_writer
from langgraph.graph import END, START, StateGraph


class ChatState(TypedDict):
    message: str


def reply(state: ChatState) -> ChatState:
    # sync node: 실제 서비스에서 ORM/sync LLM 호출이 섞이는 상황을 재현한다.
    writer = get_stream_writer()
    text = (
        f"'{state['message']}' 문의 확인했습니다. 배송 접수를 도와드릴게요. "
        "보내시는 분 성함과 받으시는 분 주소를 알려주세요."
    )
    for token in text.split(" "):
        time.sleep(0.3)
        writer(token + " ")
    return state


chat_graph = (
    StateGraph(ChatState)
    .add_node("reply", reply)
    .add_edge(START, "reply")
    .add_edge("reply", END)
    .compile()
)
