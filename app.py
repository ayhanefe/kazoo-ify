from flask import Flask, render_template, request, redirect, send_from_directory
from flask_bootstrap import Bootstrap
from werkzeug.utils import secure_filename

from spleeter.separator import Separator
from pysndfx import AudioEffectsChain
from librosa import load
from pydub import AudioSegment

import os, glob, shutil

def create_app():
  app = Flask(__name__)
  Bootstrap(app)

  return app

app = create_app()

app.config['MAX_CONTENT_LENGTH'] = 1024 * 1024 * 10
app.config['UPLOAD_EXTENSIONS'] = ['.mp3']
app.config['UPLOAD_PATH'] = 'uploads'


@app.route('/')
def hello_world():
    return render_template('index.html', song="NO")


@app.route('/', methods=['POST'])
def upload_file():
    uploaded_file = request.files['file']
    filename = secure_filename(uploaded_file.filename)
    if filename != '':
        # We only accept mp3 files
        file_ext = os.path.splitext(filename)[1]
        if file_ext not in app.config['UPLOAD_EXTENSIONS']:
            print("File type not recognized")
            abort(400)

        # Only store the last successful data
        clean_folder(app.config['UPLOAD_PATH'])

        uploaded_file.save(os.path.join(app.config['UPLOAD_PATH'], filename))
        mode = []
        mode = request.form.getlist('mode')[0] # doesnt work

        process_sound_file(os.path.join(os.path.join(app.config['UPLOAD_PATH'], filename)), app.config['UPLOAD_PATH'], mode)

    return render_template('index.html', songpath=os.path.join(app.config['UPLOAD_PATH'], filename))


@app.route('/uploads/<filename>', methods=['GET'])
def show_audio(filename):
    return send_from_directory(app.config['UPLOAD_PATH'], filename)


def clean_folder(path):
    if os.path.isdir(path):
        for filename in os.listdir(path):
            file_path = os.path.join(path, filename)
            try:
                if os.path.isfile(file_path) or os.path.islink(file_path):
                    os.unlink(file_path)
                elif os.path.isdir(file_path):
                    shutil.rmtree(file_path)
            except Exception as e:
                print('Failed to delete %s. Reason: %s' % (file_path, e))
    else:
        os.makedirs(path)


def process_sound_file(infile, outpath, mode):

    # Using embedded configuration.
    separator = Separator('spleeter:2stems')

    inpath = infile[:infile.index('/')]
    inname = infile[infile.index('/') + 1:infile.index('.')]

    separator.separate_to_file(infile, outpath)

    if (mode == 'I'):
        output = AudioSegment.from_mp3(os.path.join(os.path.join(outpath, inname), "accompaniment.wav"))
        output.export(os.path.join(outpath, inname + ".mp3"), format="mp3")
        return
    elif (mode == 'V'):
        output = AudioSegment.from_mp3(os.path.join(os.path.join(outpath, inname), "vocals.wav"))
        output.export(os.path.join(outpath, inname + ".mp3"), format="mp3")
        return

    vocals, sr = load(os.path.join(os.path.join(outpath, inname), "vocals.wav"), sr=44100)

    fx = (
        AudioEffectsChain()
        .highshelf()
        .lowpass(200)
        .tremolo(2, depth=50)
        .overdrive(gain=50, colour=100)
        .compand(threshold=-40, db_from=-40, db_to=-40)
        .lowshelf()
    )

    # Apply the effects to a ndarray and store the resulting audio to disk.
    fx(vocals, os.path.join(outpath, 'vocals.mp3'))

    # Reload the files as AudioSegments
    sound1 = AudioSegment.from_mp3(os.path.join(outpath, 'vocals.mp3'))+ 2 # Amplifies vocals
    sound2 = AudioSegment.from_mp3(os.path.join(os.path.join(outpath, inname), "accompaniment.wav"))

    # mix sound2 with sound1, starting at 5000ms into sound1)
    output = sound1.overlay(sound2, position=0)

    # save the result
    output.export(os.path.join(outpath, inname + ".mp3"), format="mp3")

    del(output)
    del(separator)
    del(vocals)
    del(sound1)
    del(sound2)
