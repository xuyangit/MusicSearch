from flaskrecognizer import FlaskRecognizer

recognizer = FlaskRecognizer()
print(recognizer.matchByWav("test.mp3"))
