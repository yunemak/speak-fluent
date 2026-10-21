import pytest

from backend.farewell import is_farewell


@pytest.mark.parametrize("text", [
    "Goodbye!", "Bye for now.", "See you later, thanks!", "Okay, that's all for today.",
    "That’s all for today.", "End the conversation.", "Please end this conversation.",
    "End the conversation, please.", "Okay, goodbye, thank you!", "Thanks, goodbye.",
    "Good bye!", "Stop the conversation.", "Goodbye for now.", "See you tomorrow.",
    "Goodbye.", "Bye.", "good bye", "I'm done.", "We are done.", "I am finished.",
    "Take care.", "Have a nice day.", "Okay then goodbye.", "Alright, goodbye.",
    "That's all.", "See ya.", "Goodby.", "Thank you goodbye.", "Goodbye, thank you.",
])
def test_clear_closing(text):
    assert is_farewell(text)


@pytest.mark.parametrize("text", [
    "My friend said goodbye yesterday.", "How do I say goodbye?", "I don't want to say goodbye.",
    "I bought a new bike.", "", "Thanks!", "Don't end the conversation.",
    "How do I end the conversation?", "He told me to end the conversation.",
    "I said goodbye yesterday.", "We talked about saying goodbye later.",
    "The good news is the weather is nice today.", "I am done with my homework, but the meeting is tomorrow.",
    "Sorry, I was saying goodbye to someone.", "Yesterday I said goodbye to my neighbour.",
])
def test_incidental_words_do_not_end_practice(text):
    assert not is_farewell(text)


@pytest.mark.parametrize("text", [
    "Goodbye. How was your day?", "Bye! What did you do?", "Goodbye, that's great.",
])
def test_a_closing_spoken_over_the_ai_voice_still_ends_practice(text):
    assert is_farewell(text)
