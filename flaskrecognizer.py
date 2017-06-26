from Dejavu import Dejavu
from recognize import FileRecognizer
class FlaskRecognizer(object):
    def __init__(self):
        self.config = {
            "database":{
                "host": "localhost",
                "user": "root",
                "passwd": "xuyang",
                "port": 3306,
                "db": "music"
            }
        }
        self.dejavu = Dejavu(self.config)
        self.dejavu.initFromMetaFile()
    def matchByWav(self, fileName):
        return self.dejavu.recognize(FileRecognizer, fileName)
    def mathByData(self, data):
        return self.dejavu.find_matches(data)