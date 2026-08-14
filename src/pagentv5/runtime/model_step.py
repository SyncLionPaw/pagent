from ..provider import messages as provider_messages


def provider_message_has_output(message: provider_messages.ProviderMessage) -> bool:
    if isinstance(message, provider_messages.TextDelta):
        return bool(message.delta)
    if isinstance(message, provider_messages.TextEnd):
        return bool(message.text)
    if isinstance(message, provider_messages.ReasoningDelta):
        return bool(message.delta)
    if isinstance(message, provider_messages.ReasoningEnd):
        return bool(message.text)
    return isinstance(
        message,
        (
            provider_messages.ToolCallStart,
            provider_messages.ToolCallDelta,
            provider_messages.ToolCallEnd,
        ),
    )


class ModelStep:
    def __init__(self) -> None:
        self.terminal: (
            provider_messages.ResponseEnd | provider_messages.ResponseError | None
        ) = None
        self.tool_calls: list[provider_messages.ToolCallEnd] = []
        self.text_deltas: dict[int, list[str]] = {}
        self.text_ends: dict[int, str] = {}
        self.has_output = False

    def add(self, message: provider_messages.ProviderMessage) -> None:
        if self.terminal is not None:
            raise RuntimeError("provider produced a message after the terminal message")

        self.has_output = self.has_output or provider_message_has_output(message)
        if isinstance(message, provider_messages.TextDelta):
            self.text_deltas.setdefault(message.content_index, []).append(message.delta)
        elif isinstance(message, provider_messages.TextEnd):
            self.text_ends[message.content_index] = message.text
        elif isinstance(message, provider_messages.ToolCallEnd):
            self.tool_calls.append(message)
        elif isinstance(
            message,
            (provider_messages.ResponseEnd, provider_messages.ResponseError),
        ):
            self.terminal = message

    def assistant_text(self) -> str:
        content_indexes = sorted(self.text_deltas.keys() | self.text_ends.keys())
        return "".join(
            self.text_ends.get(index, "".join(self.text_deltas.get(index, [])))
            for index in content_indexes
        )
