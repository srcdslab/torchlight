# Torchlight3

## 0. Requirements
 * Python3.6
 * FFMPEG
 * youtube-dl
 * On game server:
   * custom sourcemod
   * sm-ext-AsyncSocket extension
   * smjansson extension
   * SMJSONAPI plugin
   * sm-ext-Voice extension

## 1. Install
  * Install python3 and python-virtualenv
  * Create a virtualenv: `virtualenv venv`
  * Activate the virtualenv: `. venv/bin/activate`
  * Install all dependencies: `pip install -r requirements.txt`

## 2. Usage
Set up game server stuff.
Adapt config.json.

##### Make sure you are in the virtualenv! (`. venv/bin/activate`)
Run: `python main.py`
