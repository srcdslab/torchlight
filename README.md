# Torchlight3

## Requirements
 * [Python3.8+](https://github.com/python/cpython)
 * [FFMPEG](https://github.com/FFmpeg/FFmpeg)
 * [youtube-dl](https://github.com/ytdl-org/youtube-dl)
 * [dectalk](https://github.com/dectalk/dectalk)
 * On game server:
   * [sm-ext-AsyncSocket extension](https://github.com/srcdslab/sm-ext-asyncsocket)
   * [smjansson extension](https://github.com/srcdslab/sm-ext-SMJansson)
   * [SMJSONAPI plugin](https://github.com/srcdslab/sm-plugin-SMJSONAPI)
   * [sm-ext-Voice extension](https://github.com/srcdslab/sm-ext-Voice)

## Installation
### Torchlight
  * Install python3 and python-virtualenv
  * Create a virtualenv: `python3 -m venv venv`
  * Activate the virtualenv: `. venv/bin/activate`
  * Install all dependencies: `pip install -r requirements.txt`
  * Install torchlight: `pip install -e .`

Adapt the files in the config folder.

### Game server
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

## Docker
```
version: '3.7'

services:
  torchlight:
    image: ghcr.io/srcdslab/torchlight:master
    container_name: torchlight
    ports:
      - 27115:27115
    network_mode: host
    volumes:
      - /my/path/to/sounds:/app/sounds
      - /my/path/to/config:/app/config
```
