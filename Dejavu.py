# -*- coding:utf-8 -*-
from database import Database
from database_sql import SQLDatabase
import decoder as decoder
import fingerprint
import multiprocessing
import os
import traceback
import sys
import xml.etree.ElementTree as ET

class Dejavu(object):

    SONG_ID = "song_id"
    SONG_NAME = 'song_name'
    CONFIDENCE = 'confidence'
    MATCH_TIME = 'match_time'
    OFFSET = 'offset'
    OFFSET_SECS = 'offset_seconds'

    def __init__(self, config):
        super(Dejavu, self).__init__()
        self.config = config
        # initialize db
        self.db = SQLDatabase(**config.get("database", {}))
        self.db.setup()
        # if we should limit seconds fingerprinted,
        # None|-1 means use entire track
        self.limit = self.config.get("fingerprint_limit", None)
        if self.limit == -1:  # for JSON compatibility
            self.limit = None
        self.get_fingerprinted_songs()

    def get_fingerprinted_songs(self):
        # get songs previously indexed
        self.songs = self.db.get_songs()
        self.songhashes_set = set()  # to know which ones we've computed before
        for song in self.songs:
            songHash = song[Database.FIELD_FILE_SHA1]
            self.songhashes_set.add(songHash)
    def initFromMetaFile(self):
        songs = []
        nprocesses = 0
        with open("meta.txt") as f:
            lines = f.readlines()[:100]
            for line in lines:
                song = {}
                root = ET.fromstring(line)
                for child in root:
                    song[child.tag] = child.text
                filePath = "/home/xuyang/MusicSearch/XiamiMusic/" + "/" + song["singers"] + "/" + song["album__name"] + "/" + song["songName"]
                songPath = filePath + ".mp3"
                song["songPath"] = songPath
                lrcPath = filePath + ".lrc"
                songs.append(song)
        try:
            nprocesses = multiprocessing.cpu_count()
        except NotImplementedError:
            nprocesses = 1
        else:
            nprocesses = 1 if nprocesses <= 0 else nprocesses
        pool = multiprocessing.Pool(nprocesses)
        fileToFingerprint = []
        for song in songs:
            filename = song["songPath"]
            try:
                if decoder.unique_hash(filename) in self.songhashes_set:
                    continue
                fileToFingerprint.append(song)
            except Exception as e:
                print(e)
                continue
        worker_input = zip(fileToFingerprint, [self.limit] * len(fileToFingerprint))
        # Send off our tasks
        iterator = pool.imap_unordered(_fingerprint_worker, worker_input)
        # Loop till we have all of them
        while True:
            try:
                song, fileHash, hashes = iterator.next()
            except multiprocessing.TimeoutError:
                continue
            except StopIteration:
                break
            except:
                print("Failed fingerprinting")
                traceback.print_exc(file=sys.stdout)
            else:
                self.db.insert_song(song['songId'], song['songName'], fileHash)
                self.db.insert_hashes(song['songId'], hashes)
                self.db.set_song_fingerprinted(song['songId'])
                self.get_fingerprinted_songs()

        pool.close()
        pool.join()

    def find_matches(self, samples, Fs=fingerprint.DEFAULT_FS):
        hashes = fingerprint.fingerprint(samples, Fs=Fs)
        return self.db.return_matches(hashes)

    def align_matches(self, matches):
        """
            Finds hash matches that align in time with other matches and finds
            consensus about which hashes are "true" signal from the audio.

            Returns a dictionary with match information.
        """
        # align by diffs
        diff_counter = {}
        largest = 0
        largest_count = 0
        song_id = -1
        for tup in matches:
            sid, diff = tup
            if diff not in diff_counter:
                diff_counter[diff] = {}
            if sid not in diff_counter[diff]:
                diff_counter[diff][sid] = 0
            diff_counter[diff][sid] += 1

            if diff_counter[diff][sid] > largest_count:
                largest = diff
                largest_count = diff_counter[diff][sid]
                song_id = sid

        # extract idenfication
        song = self.db.get_song_by_id(song_id)
        if song:
            # TODO: Clarify what `get_song_by_id` should return.
            songname = song.get(Dejavu.SONG_NAME, None)
        else:
            return None

        # return match info
        nseconds = round(float(largest) / fingerprint.DEFAULT_FS *
                         fingerprint.DEFAULT_WINDOW_SIZE *
                         fingerprint.DEFAULT_OVERLAP_RATIO, 5)
        song = {
            Dejavu.SONG_ID : song_id,
            Dejavu.SONG_NAME : songname,
            Dejavu.CONFIDENCE : largest_count,
            Dejavu.OFFSET : int(largest),
            Dejavu.OFFSET_SECS : nseconds,
            Database.FIELD_FILE_SHA1 : song.get(Database.FIELD_FILE_SHA1, None),}
        return song

    def recognize(self, recognizer, *options, **kwoptions):
        r = recognizer(self)
        return r.recognize(*options, **kwoptions)


def _fingerprint_worker(arg):
    try:
        song, limit = arg
    except ValueError:
        pass
    channels, frameRate, fileHash = decoder.read(song['songPath'], limit)
    result = set()
    for channeln, channel in enumerate(channels):
        hashes = fingerprint.fingerprint(channel, Fs=frameRate)
        result |= set(hashes)
    return song, fileHash, result

