import pytest

from backend.farewell import is_farewell


@pytest.mark.parametrize("text", ["Goodbye!", "Bye for now.", "See you later, thanks!",
                                 "Okay, that's all for today.", "That’s all for today.",
                                 "End the conversation.", "Please end this conversation.",
                                 "End the conversation, please.", "Okay, goodbye, thank you!",
                                 "Thanks, goodbye.", "Good bye!", "Stop the conversation."])
def test_clear_closing(text):
    assert is_farewell(text)


@pytest.mark.parametrize("text", ["My friend said goodbye yesterday.", "How do I say goodbye?",
                                 "I don't want to say goodbye.", "I bought a new bike.", "", "Thanks!",
                                 "Don't end the conversation.", "How do I end the conversation?",
                                 "He told me to end the conversation.", "I said goodbye yesterday."])
def test_incidental_words_do_not_end_practice(text):
    assert not is_farewell(text)
