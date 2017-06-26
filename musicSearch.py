#coding=utf-8 
import flask_whooshalchemy
from flask import Flask
from flask import render_template
from flask import send_from_directory
from flask import make_response
from flask import request
from flask import redirect
from flask import jsonify
from gevent.wsgi import WSGIServer
from flaskrecognizer import FlaskRecognizer
from whoosh.analysis import StemmingAnalyzer
from flask_sqlalchemy import SQLAlchemy
import time
import xml.etree.ElementTree as ET

db = SQLAlchemy()
app = Flask(__name__)
host = "0.0.0.0"
port = 10001
app.config['WHOOSH_BASE'] = "/home/xuyang/MusicSearch"
app.config['SQLALCHEMY_DATABASE_URI'] = "sqlite:///music.db"
db.init_app(app)
recognizer = FlaskRecognizer()
storeRoot = "/home/xuyang/MusicSearch/"
fileRoot = "/home/xuyang/MusicSearch/XiamiMusic/"
class Song(db.Model):
  __tablename__ = 'songs'
  __searchable__ = ['songName', 'albumName', 'singers', 'songwriters', 'composer', 'lyric']  # these fields will be indexed by whoosh
  __analyzer__ = StemmingAnalyzer()
  songId = db.Column(db.Integer, primary_key=True)
  songName = db.Column(db.Text)
  albumId = db.Column(db.Integer)
  albumName = db.Column(db.Text)
  singers = db.Column(db.Text)
  artistId = db.Column(db.Integer)
  songwriters = db.Column(db.Text)
  composer = db.Column(db.Text)
  lyric = db.Column(db.Text)
  playCount = db.Column(db.Integer)

  def __getitem__(self, item):
        return getattr(self, item)
  def as_dict(self):
       return {c.name: getattr(self, c.name) for c in self.__table__.columns}

class User(db.Model):
  __tablename__ = 'user'
  id = db.Column(db.Text, primary_key=True)
  firstname = db.Column(db.Text)
  lastname = db.Column(db.Text)
  eaddress = db.Column(db.Text)
  password = db.Column(db.Text)

  def __getitem__(self, item):
        return getattr(self, item)
  def as_dict(self):
       return {c.name: getattr(self, c.name) for c in self.__table__.columns}

class UserPref(db.Model):
  __table__name = 'userpref'
  userId = db.Column(db.Text, primary_key=True)
  keyword = db.Column(db.Text, primary_key=True)
  singer = db.Column(db.Text, primary_key=True)
  freq = db.Column(db.Integer)
  
  def __getitem__(self, item):
        return getattr(self, item)
  def as_dict(self):
       return {c.name: getattr(self, c.name) for c in self.__table__.columns}

#this is built once when you firstly init the index
def buildTable():
    with app.app_context():
        with open("meta.txt") as f:
            for line in f:
                song = {}
                root = ET.fromstring(line)
                for child in root:
                    song[child.tag] = child.text
                filePath = fileRoot + song["singers"] + "/" + song["album__name"] + "/" + song["songName"]
                db.session.add(Song(
                    songId=song["songId"], songName=song["songName"],
                    albumId=song["albumId"], albumName=song["album__name"],
                    singers=song["singers"], artistId=song["artistId"],
                    songwriters=song["songwriters"], composer=song["composer"],
                    lyric=simplifyLrc(filePath + ".lrc"), playCount=song["playCount"]
                    ))
                db.session.commit()
def simplifyLrc(fileName):
    with open(fileName) as f:
        res = ""
        for line in f:
            i = 0
            line = line.lower()
            flag = True
            while(i < len(line)):
                if(line[i] == '['):
                    flag = False
                elif(line[i] == ']'):
                    flag = True
                if(flag and ((line[i] >= 'a' and line[i] <= 'z') or line[i] == ' ')):
                    res += line[i]
                i += 1
            res += ' '
    return removeDupBlanks(res)
def removeDupBlanks(s):
    i = 0
    res = ""
    while(i < len(s)):
        if(s[i] == ' '):
            if(i == 0):
                pass
            elif(s[i - 1] == ' '):
                pass
            else:
                res += ' '
        else:
            res += s[i]
        i += 1
    return res
def queryByKeyword(word):
    with app.app_context():
        results = list(Song.query.whoosh_search(word).all())
        print results
        for result in results:
            print result.songName
def initIndex():
  with app.app_context():
      db.create_all()
      flask_whooshalchemy.whoosh_index(app, Song)
def distinct(records, name):
  tp = set()
  res = []
  for r in records:
    if(not r[name] in tp):
      res.append(r)
      tp.add(r[name])
  return res

#queryByKeyword("devil run")
#code for server
@app.route("/")
@app.route("/home")
def home():
  return render_template("Home.html")

@app.route("/login")
def login():
    return render_template("Login.html")
  
@app.route("/loginUser", methods=["POST"])
def userLogin():
    userid = request.form['userid']
    password = request.form['password']
    result = None
    with app.app_context():
        try:
            result = db.session.query(User).filter(User.id == userid, User.password == password).first()
        finally:
            if(result == None):
                return jsonify(err = 'invalid', redirect = '')
            else:
                response = make_response(jsonify(err = '', redirect = 'home'))
                response.set_cookie('userid', userid)
                return response
    return jsonify(err = 'invalid', redirect = '')
  
@app.route("/register/validation", methods=["POST"])
def registerValid():
    data = request.get_json()
    result = None
    field = data['field']
    with app.app_context():
        if(field == "email"):
            try:
                result = db.session.query(User).filter(User.eaddress == data['data']).first()
            finally:
                if(result != None):
                     return 'EMAIL_ALREADY_EXIST'
                else:
                    return ''
        elif(field == "id"):
            try:
                result = db.session.query(User).filter(User.id == data['data']).first()
            finally:
                if(result != None):
                    return "USERNAME_ALREADY_EXIST"
                else:
                    return ''
        else:
            return ''
      
@app.route("/register", methods=['GET','POST'])
def register():
    if request.method == 'POST':
        firstname = request.form['firstname']
        lastname = request.form['lastname']
        userid = request.form['userid']
        eaddress = request.form['eaddress']
        password = request.form['password']
        try:
            with app.app_context():
                db.session.add(User(
                    id=userid, firstname=firstname, lastname=lastname,
                    eaddress=eaddress, password=password
                    ))
                db.session.commit()
        finally:
            return jsonify(err = '', redirect = 'login')
    else:
        return render_template("Register.html")
@app.route("/getMp3/<path:path>")
def getMp3(path):
  paths = path.split('/')
  return send_from_directory(fileRoot + paths[0] + "/" + paths[1], paths[2])
@app.route("/getPic/<path:path>")
def getPic(path):
  paths = path.split('/')
  return send_from_directory(fileRoot + paths[0] + "/" + paths[1], paths[2])
@app.route("/getSongInfo", methods=['GET'])
def getSongInfo():
  songId = request.args.get('songId')
  userid = request.cookies.get('userid')
  keyword = request.cookies.get('keyword')
  result = None
  with app.app_context():
      result = db.session.query(Song).filter(Song.songId == int(songId)).first()
      if(result == None):
        return jsonify(host=host, result=result)
      filePath = fileRoot + result["singers"] + "/" + result["albumName"] + "/" + result["songName"] + ".lrc"
      with open(filePath) as f:
        s = ""
        for line in f:
          s += line
        result.lyric = s
  with app.app_context():
    if(userid != None and keyword != None and userid != '' and keyword != ''):
      keyword = keyword.lower()
      res = db.session.query(UserPref).filter(UserPref.userId == userid, UserPref.keyword == keyword, UserPref.singer == result["singers"]).first()
      if(res == None):
        db.session.add(UserPref(
          userId=userid, keyword=keyword, singer=result["singers"], freq=1))
        db.session.commit()
      else:
        res.freq += 1
        db.session.commit()  
  return jsonify(host=host, result=result.as_dict())
@app.route("/getAlbum", methods=['GET'])
def getAlbum():
  albumName = request.args.get('albumName')
  if(albumName == None or albumName == ''):
    return jsonify(err='albumName is none')
  with app.app_context():
    result = db.session.query(Song).filter(Song.albumName == albumName).all()
    if(result != None and len(result) != 0):
      return render_template("Album.html", data=[x.as_dict() for x in result])
    else:
      return jsonify(err='no results for this album')
@app.route("/getSinger", methods=["GET"])
def getSinger():
  singers = request.args.get('singers')
  if(singers == None or singers == ''):
    return jsonify(err='singers is none')
  with app.app_context():
    result = db.session.query(Song).filter(Song.singers == singers).all()
    if(result != None and len(result) != 0):
      return render_template("Singer.html", data=[x.as_dict() for x in result])
    else:
      return jsonify(err='no results for this singer')
@app.route("/getSong", methods=['GET'])
def getSong():
  songId = request.args.get('songId')
  if(songId == None or songId == ''):
    return jsonify(err="songId is none")
  with app.app_context():
    result = db.session.query(Song).filter(Song.songId == int(songId)).first()
    filePath = fileRoot + result["singers"] + "/" + result["albumName"] + "/" + result["songName"] + ".lrc"
    with open(filePath) as f:
      s = ""
      for line in f:
        s += line
      result.lyric = s
    picUrl = "https://202.120.32.216:10001" + "/getPic/" + result["singers"] + "/" + result["albumName"] + "/" + result["songName"] + ".jpg"
    mp3Url = "https://202.120.32.216:10001" + "/getMp3/" + result["singers"] + "/" + result["albumName"] + "/" + result["songName"] + ".mp3"
    return render_template("Song.html", data=result.as_dict(), picUrl=picUrl, mp3Url=mp3Url)
@app.route("/userinfo")
def getUser():
  return "1"
@app.route("/exit")
def userExit():
  return "1"
@app.route("/searchBySeg", methods=["POST"])
def searchBySeg():
  uploadFile = request.files['data']
  res = None
  fileName = storeRoot + time.strftime('%Y-%m-%d-%H-%M-%S', time.localtime(time.time())) + ".mp3"
  try:
    uploadFile.save(fileName)
    res = recognizer.matchByWav(fileName)
  except Exception as e:
    return jsonify(err=str(e))
  else:
    if(res != None):
      with app.app_context():
        return redirect("https://202.120.32.216:10001/getSong?songId=" + str(res['song_id']))
    else:
      return jsonify(err="noneresult")
@app.route("/searchByWav", methods=["POST"])
def searchByWav():
  uploadFile = request.files['data']
  res = None
  fileName = storeRoot + time.strftime('%Y-%m-%d-%H-%M-%S', time.localtime(time.time())) + ".wav"
  try:
    uploadFile.save(fileName)
    res = recognizer.matchByWav(fileName)
  except Exception as e:
    return jsonify(err=str(e), redirect='')
  else:
    if(res != None):
      with app.app_context():
        return jsonify(err="", redirect="https://202.120.32.216:10001/getSong?songId=" + str(res['song_id']))
    else:
      return jsonify(err="noneresult", redirect='')
@app.route("/searchAll", methods=["POST"])
def searchAll():
  name = request.form['queryword']
  userid = request.cookies.get('userid')
  data = {}
  if(name == None or len(name) == 0):
    data['resultBySinger'] =[] 
    data['resultBySongName'] = []
    data['resultByAlbum'] = []
    data['resultByComposer'] = []
    return render_template("Search.html", data=data)
  name = name.lower()
  with app.app_context():
    resultBySinger = [x.as_dict() for x in Song.query.whoosh_search(name, limit=500, fields=("singers",)).all()]
    resultBySongName = [x.as_dict() for x in Song.query.whoosh_search(name, limit=500, fields=("songName", "lyric", )).all()]
    resultByAlbum = [x.as_dict() for x in set(Song.query.whoosh_search(name, limit=500, fields=("albumName", )).all())]
    resultByComposer = [x.as_dict() for x in set(Song.query.whoosh_search(name, limit=500, fields=("composer", "songwriters", )).all())]
    if(userid != None and userid != ''):
      res = db.session.query(UserPref).filter(UserPref.userId == userid,
                                              UserPref.keyword == name,
                                              UserPref.freq >= 3).all()
      singerFreqMap = {}
      for r in res:
        singerFreqMap[r.singer] = r.freq
      resultBySongName = sorted(resultBySongName, cmp=lambda x, y: singerFreqMap[y['singers']] - singerFreqMap[x['singers']] if(x['singers'] in singerFreqMap and y['singers'] in singerFreqMap) else
                              (
                                ((x['singers'] in singerFreqMap) and -singerFreqMap[x['singers']])
                              or ((y['singers'] in singerFreqMap) and singerFreqMap[y['singers']]))
                              or (y['playCount'] - x['playCount'])
                              )
      
  data['resultBySinger'] = distinct(resultBySinger, "singers")
  data['resultBySongName'] = resultBySongName
  data['resultByAlbum'] = distinct(resultByAlbum, "albumName")
  data['resultByComposer'] = resultByComposer
  return render_template("Search.html", data=data)
@app.route("/searchBySongname", methods=["POST"])
def searchByName():
  name = request.form['queryword']
  results = list(Song.query.whoosh_search(name, fields=("songName", "lyric", )).all())
  return jsonify(results=results)
@app.route("/searchBySinger", methods=["POST"])
def searchBySinger():
  singerName = request.form['queryword']
  results = list(Song.query.whoosh_search(singerName, fields=("singers",)).all())
  return jsonify(singers=[x.singers for x in results])
  
if __name__ == "__main__":
  initIndex()
  http_server = WSGIServer((host, port), app, keyfile=storeRoot + 'server.key', certfile=storeRoot + 'server.crt')
  http_server.serve_forever()
  #app.run(port=port, host=host, ssl_context=(storeRoot + "server.crt", storeRoot + "server.key"))
