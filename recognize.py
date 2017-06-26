import fingerprint as fingerprint
import decoder as decoder
import numpy as np
import pyaudio
import time

class FileRecognizer(object):
    def __init__(self, dejavu):
        self.dejavu = dejavu
        self.Fs = fingerprint.DEFAULT_FS

    def _recognize(self, *data):
        matches = []
        for d in data:
            matches.extend(self.dejavu.find_matches(d, Fs=self.Fs))
        return self.dejavu.align_matches(matches)

    def recognize_file(self, filename):
        frames, self.Fs, file_hash = decoder.read(filename, self.dejavu.limit)
        t = time.time()
        match = self._recognize(*frames)
        t = time.time() - t
        if match:
            match['match_time'] = t

        return match

    def recognize(self, filename):
        return self.recognize_file(filename)
