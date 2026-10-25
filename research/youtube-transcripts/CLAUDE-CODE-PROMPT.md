Download English transcripts for the YouTube videos listed in `video-links.txt` in this folder, and turn them into plain text.

1. Check that Python 3 is installed. Install yt-dlp with `python3 -m pip install --user -U yt-dlp` (on Windows: `py -m pip install --user -U yt-dlp`). If `yt-dlp` isn't on the PATH afterwards, use `python3 -m yt_dlp` instead.

2. Make a folder `vtt` and run, from this folder:

   ```
   yt-dlp --skip-download --write-subs --write-auto-subs --sub-langs "en.*" --sub-format vtt --sleep-requests 2 --sleep-subtitles 2 --ignore-errors -o "vtt/%(id)s.%(ext)s" --print-to-file "%(id)s	%(title)s	%(channel)s" titles.tsv -a video-links.txt
   ```

   Download subtitles only, never the videos. Don't pass browser cookies, and don't use proxies or VPNs. If YouTube answers "Too Many Requests" or "confirm you're not a bot", stop. Wait about 30 minutes, then run the same command again: it skips videos that are already done.

3. For each video, keep one subtitle file. Prefer one written by a person (`.en.vtt`) over an automatic one (`.en-orig.vtt` or other `.en-*` files). Convert it to plain text: drop the `WEBVTT` header, timestamps, cue numbers and tags such as `<c>` or `<00:00:01.000>`. Remove the repeated lines that automatic captions produce, where each cue repeats the line before it. Join the rest into paragraphs, starting a new paragraph after a gap of more than 3 seconds.

4. Write each transcript to `txt/<video id>.txt`, starting with these three lines and a blank line:

   ```
   URL: https://www.youtube.com/watch?v=<video id>
   Title: <title>
   Channel: <channel>
   ```

5. Write `missing.txt`, listing every link from `video-links.txt` that has no transcript, each with the reason (no English subtitles, video removed or private, error message).

6. Zip the `txt` folder plus `missing.txt` into `transcripts.zip`. Tell me how many transcripts you got and how many are missing.

Don't change any files outside this folder.
