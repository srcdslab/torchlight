# Torchlight

Bot for source engine games with a lot of commands:
  * Play music from youtube, mp3, wav
  * Get the weather in real time.
  * Play tts messages
  * And much more!

> [!IMPORTANT]
> You need to run SMJSONAPI 1.1.x at minimum in order to have all features working properly

## Requirements
### Linux
  * [Python3.10+](https://github.com/python/cpython)
  * [FFMPEG](https://github.com/FFmpeg/FFmpeg)
  * [youtube-dl](https://github.com/ytdl-org/youtube-dl)
  * [dectalk](https://github.com/dectalk/dectalk)

### Game server
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

## Running torchlight
```
torchlight
```
You can find more information about available commands with
```
torchlight --help
```

## YouTube Cookies

In some environments (VPS, dedicated servers, VPN/WARP containers), YouTube search may fail due to rate limits or bot protection.  
Providing a valid YouTube cookie file can resolve this issue.

Configure the cookie file in:

`Sounds > CookieFile`

inside your JSON configuration.

---

### How to Get YouTube Cookies

1. Install a browser extension that exports cookies in **Netscape format (`cookies.txt`)**
   - Chrome: **Get cookies.txt LOCALLY**
   - Firefox: **cookies.txt**

2. Open https://youtube.com and make sure you are logged in.

3. Use the extension to export cookies for `youtube.com`.

4. Save the file as:

   ```
   cookies.txt
   ```

5. Upload it to your server (example):

   ```
   /app/config/cookies.txt
   ```

6. Set the path in your configuration:

   ```json
   {
     "YoutubeSearch": {
      "parameters": {
          "proxy": "",
          "keywords_banned": [],
          "cookies": "config/cookies.txt"
      }
     }
   }
   ```

7. Restart the container after updating the configuration.

8. It's preferred to use **Cloudflare WARP** (recommended for VPS environments), you can run it using:  
   https://github.com/cmj2002/warp-docker  

   Then configure Torchlight to use the WARP container's socks5 proxy:

   ```yaml
   "proxy": "socks5://0.0.0.0:PORT"
   ```

   This routes all requests through WARP, which helps prevent YouTube blocking server IP addresses.
---

### Myinstants

To play sounds from myinstants website (!mi) you need to install `FlareSolverr`
Link: https://github.com/Flaresolverr/Flaresolverr

Follow the steps of its installation.

After that, specify its Host and Port on the config.json file:
```yaml
"FlareSolverr"
{
  "Host": "127.0.0.1",
  "Port": 8191
},
```
If you are using docker for torchlight, please specify `Host` as the main server's public IP.
`8191` is just the default port used on `FlareSolverr`

### Notes

- Keep your cookie file private (it contains session authentication data).
- If YouTube search stops working, export fresh cookies.
- Do **not** share your cookie file publicly.

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
