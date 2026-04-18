import os
import re
import numpy as np
from moviepy import (
    VideoFileClip,
    TextClip,
    CompositeVideoClip,
    ColorClip
)
from moviepy.video.fx import FadeIn, FadeOut





def parse_lrc(lrc_text):
    lines = lrc_text.split("\n")
    parsed = []

    for line in lines:
        if "]" in line:
            try:
                time_part, text = line.split("]", 1)
                time_part = time_part.replace("[", "").strip()

                m, s = time_part.split(":")
                seconds = int(m) * 60 + float(s)

                text = text.strip()

                # 🚫 Skip empty text
                if not text:
                    continue

                # 🚫 Skip pseudo labels like [Verse 1], [Chorus], etc.
                if re.match(r"^\[.*\]$", text):
                    continue

                parsed.append({
                    "time": seconds,
                    "text": text
                })

            except:
                continue

    return parsed


def create_text_clip(text, start, end, video_w, video_h):

    txt = TextClip(
        text=text,
        font_size=24,
        font="C:/Windows/Fonts/arialbd.ttf",
        color="white",
        stroke_color="black",
        stroke_width=2,
        method="caption",
        size=(int(video_w * 0.95), 50)
    )

    txt = (
        txt
        .with_start(start)
        .with_end(end)
        .with_effects([
            FadeIn(0.3),
            FadeOut(0.3)
        ])
        .with_position(lambda t: (
            "center",
            video_h - txt.h - 20   # 👈 always stays inside frame
        ))
    )

    return txt



def add_lyrics_to_video(video_path, lrc_text, output_path=None):

    if not os.path.exists(video_path):
        raise FileNotFoundError(f"Video not found: {video_path}")

    subtitles = parse_lrc(lrc_text)

    video = VideoFileClip(video_path)

    clips = [video]

    for i in range(len(subtitles)):
        start = subtitles[i]["time"]
        end = subtitles[i+1]["time"] if i+1 < len(subtitles) else video.duration

        text = subtitles[i]["text"]

        if not text.strip():
            continue

        # 🔲 Background strip
        bg = (
            ColorClip(
                size=(video.w, 100),
                color=(0, 0, 0)
            )
            .with_opacity(0.0)
            .with_start(start)
            .with_end(end)
            .with_position(("center", video.h - 120))
        )

        txt_clip = create_text_clip(
            text,
            start,
            end,
            video.w,
            video.h
        )

        clips.append(bg)
        clips.append(txt_clip)

    final = CompositeVideoClip(clips)

    # Output path handling
    if output_path is None:
        base, ext = os.path.splitext(video_path)
        output_path = base + "_lyrics.mp4"

    final.write_videofile(
        output_path,
        fps=60,
        codec="libx264",
        audio_codec="aac",
        bitrate="5000k",
    )

    return output_path