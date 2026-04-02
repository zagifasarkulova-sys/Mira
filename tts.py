import io
from gtts import gTTS


def word_to_voice(word: str) -> io.BytesIO:
    tts = gTTS(text=word, lang="en", slow=False)
    buf = io.BytesIO()
    tts.write_to_fp(buf)
    buf.seek(0)
    buf.name = "word.mp3"
    return buf
