# Torchlight3

## 0. Requirements
 * Python3.6
 * FFMPEG
 * youtube-dl
 * On game server:
   * [custom sourcemod](https://github.com/BotoX/sourcemod)
   * [sm-ext-AsyncSocket extension](https://git.botox.bz/CSSZombieEscape/sm-ext-AsyncSocket)
   * [smjansson extension](https://forums.alliedmods.net/showthread.php?t=184604)
   * [SMJSONAPI plugin](https://git.botox.bz/CSSZombieEscape/sm-plugins/src/branch/master/SMJSONAPI) or [here](https://cloud.botox.bz/s/TDRq7XwMFmW8NeQ)
   * [sm-ext-Voice extension](https://git.botox.bz/CSSZombieEscape/sm-ext-Voice)

## 1. Install
  * Install python3 and python-virtualenv
  * Create a virtualenv: `python3 -m venv venv`
  * Activate the virtualenv: `. venv/bin/activate`
  * Install all dependencies: `pip install -r requirements.txt`

## 2. Usage
Set up game server stuff.

You need to have SourceTV enabled and use the vaudio_celt voice codec:  
`cstrike/cfg/autoexec.cfg `
```
// Server Cvars
sv_consistency 0
sv_pure -1

// Source TV
tv_allow_camera_man 0
tv_autorecord 0
tv_delay 0
tv_enable 1
tv_maxclients 16
tv_maxrate 0
tv_name "TorchTV"
tv_transmitall 1
tv_chattimelimit 1

sv_voicecodec "vaudio_celt"

map de_dust2
```

Don't put `+map` into your startup cmdline.

Adapt config.json.

##### Make sure you are in the virtualenv! (`. venv/bin/activate`)
Run: `python main.py`


### Dectalk
  * Install wine
  * Run as normal user (not root)
  * Run torchlight with: `xvfb-run -a python main.py`
