from notekeeper.application import ConsoleLogEvent, ConsoleLogSource
from notekeeper.infrastructure.runtime import InMemoryConsoleLogEventHub
from notekeeper.infrastructure.runtime.jobs import (
    ProcessLogStream,
    ProcessMessageWriter,
)


class FakeConnection:
    def __init__(self) -> None:
        self.messages: list[tuple[str, object]] = []
        self.closed = False

    def send(self, message: tuple[str, object]) -> None:
        self.messages.append(message)

    def close(self) -> None:
        self.closed = True


def test_process_log_stream_sends_complete_and_flushed_lines() -> None:
    connection = FakeConnection()
    writer = ProcessMessageWriter(connection)  # type: ignore[arg-type]
    stream = ProcessLogStream(writer, "job-123", ConsoleLogSource.STDOUT)

    stream.write("first\nsecond")
    stream.write(" part\rthird\n")
    stream.flush()

    assert connection.messages == [
        (
            "log",
            ConsoleLogEvent("job-123", ConsoleLogSource.STDOUT, "first"),
        ),
        (
            "log",
            ConsoleLogEvent("job-123", ConsoleLogSource.STDOUT, "second part"),
        ),
        (
            "log",
            ConsoleLogEvent("job-123", ConsoleLogSource.STDOUT, "third"),
        ),
    ]


def test_console_log_event_hub_subscribes_and_unsubscribes() -> None:
    hub = InMemoryConsoleLogEventHub()
    received: list[ConsoleLogEvent] = []
    unsubscribe = hub.subscribe(received.append)
    first = ConsoleLogEvent("job-1", ConsoleLogSource.STDERR, "warning")
    second = ConsoleLogEvent(None, ConsoleLogSource.LOGGING, "application")

    hub.publish(first)
    unsubscribe()
    hub.publish(second)

    assert received == [first]
