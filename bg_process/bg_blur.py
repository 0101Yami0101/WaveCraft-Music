import subprocess

def blur_video(input_path, output_path):
    FFMPEG_PATH = r"D:\CODE\Python\Projects\YTAuto\ffmpeg\ffmpeg.exe"

    cmd = [
        FFMPEG_PATH,
        "-y",
        "-i", input_path,
        "-vf", "gblur=sigma=12,scale=1280:720,eq=brightness=-0.1:saturation=1.3",
        "-c:a", "copy",
        output_path
    ]

    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    print(f"🎥 Blurred BG video created: {output_path}")

    return output_path