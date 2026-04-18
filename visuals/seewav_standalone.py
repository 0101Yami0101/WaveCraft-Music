import argparse
import json
import math
import subprocess as sp
import sys
import tempfile
from pathlib import Path
from typing import Tuple, List, Optional

try:
    import cairo
    import numpy as np
    import tqdm
except ImportError as e:
    print(f"Error: Missing required package. Install with: pip install numpy pycairo tqdm", file=sys.stderr)
    print(f"Details: {e}", file=sys.stderr)
    sys.exit(1)

__version__ = "0.1.1"
_is_main = False

# ============================================================================
# CONFIGURE FFMPEG PATHS HERE
# ============================================================================
# Change these paths to match your ffmpeg installation
FFPROBE_PATH = r"D:\CODE\Python\Projects\YTAuto\ffmpeg\ffprobe.exe"
FFMPEG_PATH = r"D:\CODE\Python\Projects\YTAuto\ffmpeg\ffmpeg.exe"
# ============================================================================

# Color animation speed - controls cycle duration
# Adjusted for 5-10 second cycles per palette change
COLOR_ANIMATION_SPEED = 0.6  # ~10 second cycle per palette


# ============================================================================
# VIBRANT COLOR PALETTES
# ============================================================================
# Each palette has 2 colors for gradient (start, end)
# All colors are highly saturated and bright
COLOR_PALETTES = [
    # Palette 1: Neon Pink to Cyan
    ((1.0, 0.0, 0.5), (0.0, 1.0, 1.0)),
    
    # Palette 2: Electric Purple to Lime
    ((1.0, 0.0, 1.0), (0.0, 1.0, 0.0)),
    
    # Palette 3: Fiery Orange to Sky Blue
    ((1.0, 0.5, 0.0), (0.0, 0.7, 1.0)),
    
    # Palette 4: Hot Red to Neon Yellow
    ((1.0, 0.0, 0.0), (1.0, 1.0, 0.0)),
    
    # Palette 5: Deep Magenta to Bright Green
    ((1.0, 0.0, 0.8), (0.0, 1.0, 0.3)),
    
    # Palette 6: Cyan to Hot Pink
    ((0.0, 1.0, 1.0), (1.0, 0.0, 0.5)),
    
    # Palette 7: Lime Green to Electric Purple
    ((0.0, 1.0, 0.0), (1.0, 0.0, 1.0)),
    
    # Palette 8: Ocean Blue to Sunset Orange
    ((0.0, 0.5, 1.0), (1.0, 0.6, 0.0)),
]


def colorize(text: str, color: int) -> str:
    """
    Wrap `text` with ANSI `color` code.
    See: https://stackoverflow.com/questions/4842424/list-of-ansi-color-escape-sequences
    """
    code = f"\033[{color}m"
    restore = "\033[0m"
    return "".join([code, text, restore])


def fatal(msg: str) -> None:
    """
    Display an error message and abort if this module is __main__.
    """
    if _is_main:
        head = "error: "
        if sys.stderr.isatty():
            head = colorize("error: ", 1)
        print(head + str(msg), file=sys.stderr)
        sys.exit(1)


def read_info(media: Path) -> dict:
    """
    Return metadata about the media file using ffprobe.
    """
    try:
        proc = sp.run(
            [
                FFPROBE_PATH, "-loglevel", "error",
                str(media), '-print_format', 'json', '-show_format', '-show_streams'
            ],
            capture_output=True,
            text=False,
            check=False
        )
        if proc.returncode:
            raise IOError(f"{media} does not exist or is of a wrong type.")
        return json.loads(proc.stdout.decode('utf-8'))
    except FileNotFoundError:
        raise IOError(f"ffprobe not found at: {FFPROBE_PATH}\nPlease update FFPROBE_PATH in the script.")


def read_audio(audio: Path, seek: Optional[float] = None, duration: Optional[float] = None) -> Tuple[np.ndarray, float]:
    """
    Read the audio file, starting at `seek` (or 0) seconds for `duration` (or all) seconds.
    Returns tuple of (float[channels, samples], samplerate).
    """
    info = read_info(audio)
    channels = None
    stream = info['streams'][0]
    
    if stream["codec_type"] != "audio":
        raise ValueError(f"{audio} should contain only audio.")
    
    channels = stream['channels']
    samplerate = float(stream['sample_rate'])

    # Build ffmpeg command
    command = [FFMPEG_PATH, '-y']
    command += ['-loglevel', 'error']
    if seek is not None:
        command += ['-ss', str(seek)]
    command += ['-i', str(audio)]
    if duration is not None:
        command += ['-t', str(duration)]
    command += ['-f', 'f32le']
    command += ['-']

    try:
        proc = sp.run(command, check=True, capture_output=True)
    except FileNotFoundError:
        raise IOError(f"ffmpeg not found at: {FFMPEG_PATH}\nPlease update FFMPEG_PATH in the script.")
    
    wav = np.frombuffer(proc.stdout, dtype=np.float32)
    return wav.reshape(-1, channels).T, samplerate


def sigmoid(x: np.ndarray) -> np.ndarray:
    """Sigmoid activation function."""
    return 1 / (1 + np.exp(-x))


def envelope(wav: np.ndarray, window: int, stride: int) -> np.ndarray:
    """
    Extract the envelope of the waveform using average pooling.
    """
    wav = np.pad(wav, window // 2)
    out = []
    for off in range(0, len(wav) - window, stride):
        frame = wav[off:off + window]
        out.append(np.maximum(frame, 0).mean())
    out = np.array(out)
    # Audio compressor based on sigmoid
    out = 1.9 * (sigmoid(2.5 * out) - 0.5)
    return out


def clamp_color(r: float, g: float, b: float) -> Tuple[float, float, float]:
    """Clamp RGB values to [0, 1] range."""
    return (
        max(0.0, min(1.0, r)),
        max(0.0, min(1.0, g)),
        max(0.0, min(1.0, b))
    )


def interpolate_color(
    c1: Tuple[float, float, float],
    c2: Tuple[float, float, float],
    t: float
) -> Tuple[float, float, float]:
    """Interpolate between two colors."""
    return (
        c1[0] * (1 - t) + c2[0] * t,
        c1[1] * (1 - t) + c2[1] * t,
        c1[2] * (1 - t) + c2[2] * t,
    )


def load_frame_as_surface(image_path: Path, width: int, height: int) -> cairo.ImageSurface:
    """
    Load a video/image frame and return it as a cairo ImageSurface.
    Scales to the specified dimensions.
    """
    from PIL import Image
    
    img = Image.open(str(image_path)).convert('RGB')
    img = img.resize((width, height), Image.Resampling.LANCZOS)
    
    # Convert PIL image to cairo surface using ARGB32 format
    # Create a surface first, then draw the image onto it
    surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, width, height)
    ctx = cairo.Context(surface)
    
    # Convert PIL image to RGBA for proper cairo compatibility
    img_rgba = img.convert('RGBA')
    pixel_data = img_rgba.tobytes('raw', 'RGBA')
    
    # Create an image surface with proper stride
    stride = cairo.ImageSurface.format_stride_for_width(cairo.FORMAT_ARGB32, width)
    img_surface = cairo.ImageSurface.create_for_data(
        bytearray(pixel_data),
        cairo.FORMAT_ARGB32,
        width,
        height,
        stride
    )
    
    # Paint the image onto our surface
    ctx.set_source_surface(img_surface, 0, 0)
    ctx.paint()
    
    return surface


def extract_video_frames(video_path: Path, tmp: Path, rate: int, duration: float, size: Tuple[int, int]) -> List[Path]:
    """
    Extract video frames using ffmpeg and return list of frame paths.
    Frames are extracted at the specified rate and scaled to size.
    """
    print(f"Extracting video frames from {video_path}...")
    
    frames_dir = tmp / "video_frames"
    frames_dir.mkdir(exist_ok=True)
    
    try:
        sp.run(
            [
                FFMPEG_PATH, "-y", "-loglevel", "error",
                "-i", str(video_path),
                "-vf", f"scale={size[0]}:{size[1]}:force_original_aspect_ratio=decrease,pad={size[0]}:{size[1]}:(ow-iw)/2:(oh-ih)/2",
                "-r", str(rate),
                "-t", str(duration),
                str(frames_dir / "%06d.png")
            ],
            check=True
        )

    except FileNotFoundError:
        raise IOError(f"ffmpeg not found at: {FFMPEG_PATH}\nPlease update FFMPEG_PATH in the script.")
    except sp.CalledProcessError as e:
        raise IOError(f"Failed to extract video frames. Error code: {e.returncode}")
    
    # Return sorted list of frame paths
    frame_paths = sorted(frames_dir.glob("*.png"))
    if not frame_paths:
        raise IOError(f"No frames extracted from video: {video_path}")
    
    return frame_paths


def draw_env(
    envs: List[np.ndarray],
    out: Path,
    fg_colors: Tuple,
    bg_color: Tuple,
    size: Tuple[int, int],
    time_factor: float = 0.0,
    bg_video_frame: Optional[Path] = None,
    intensity=0.0 
) -> None:
    """
    Draw a single frame using cairo and save it as PNG.
    envs: list of envelopes (one per channel)
    fg_colors: tuple of (r,g,b) color tuples for gradient start and end
    bg_color: (r,g,b) background color (used if bg_video_frame is None)
    size: (width, height) in pixels
    time_factor: time in seconds for color animation
    bg_video_frame: Path to background video frame (optional)
    """
    surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, *size)
    ctx = cairo.Context(surface)


    # Draw background
    if bg_video_frame and bg_video_frame.exists():
        try:
            # Load and paint the video frame as background
            bg_surface = load_frame_as_surface(bg_video_frame, *size)
            ctx.set_source_surface(bg_surface, 0, 0)
            ctx.paint()
        except Exception as e:
            print(f"Warning: Failed to load background frame {bg_video_frame}: {e}")
            # Fall back to solid background color
            ctx.set_source_rgb(*bg_color)
            ctx.rectangle(0, 0, 1, 1)
            ctx.fill()
    else:
        # Draw solid background color
        ctx.set_source_rgb(*bg_color)
        ctx.rectangle(0, 0, 1, 1)
        ctx.fill()
        
    ctx.scale(*size)

    K = len(envs)  # Number of waves to draw
    T = len(envs[0])  # Number of time steps
    pad_ratio = 0.1  # Spacing ratio between bars
    width = 1. / (T * (1 + 2 * pad_ratio))
    pad = pad_ratio * width
    delta = 2 * pad + width

    # ========================================================================
    # UPDATED: Animate between multiple vibrant color palettes
    # ========================================================================
    # Determine which palette to use and transition amount
    num_palettes = len(COLOR_PALETTES)
    
    # Smooth cycling through all palettes
    palette_position = (time_factor * COLOR_ANIMATION_SPEED) % num_palettes
    current_palette_idx = int(palette_position)
    next_palette_idx = (current_palette_idx + 1) % num_palettes
    palette_blend = palette_position - current_palette_idx  # 0 to 1
    
    # Get current and next palettes
    current_palette = COLOR_PALETTES[current_palette_idx]
    next_palette = COLOR_PALETTES[next_palette_idx]
    
    # Blend between palettes (smooth transition)
    base1 = interpolate_color(current_palette[0], next_palette[0], palette_blend)
    base2 = interpolate_color(current_palette[1], next_palette[1], palette_blend)
    
    # Use HSV-style rotation for extra vibrance variation within each palette
    hue_shift = (math.sin(time_factor * COLOR_ANIMATION_SPEED * 3) + 1) / 2
    
    # Create slightly rotated colors for internal animation
    c1 = interpolate_color(base1, base2, hue_shift * 0.3)
    c2 = interpolate_color(base2, base1, (1 - hue_shift) * 0.3)
    
    # Ensure all colors are vibrant (clamp to [0, 1])
    c1 = clamp_color(c1[0], c1[1], c1[2])
    c2 = clamp_color(c2[0], c2[1], c2[2])
    # ========================================================================

    ctx.set_line_width(width)
    for step in range(T):
        for i in range(K):
            half = 0.5 * envs[i][step]  # Height of bar
            half /= K  # Stack K waves vertically
            midrule = 0.5  # Center waveform vertically
            
            # Calculate gradient color based on bar position
            t = step / T
            r = c1[0] * (1 - t) + c2[0] * t
            g = c1[1] * (1 - t) + c2[1] * t
            b = c1[2] * (1 - t) + c2[2] * t
            
            # Draw bar upper half
            ctx.set_source_rgb(r, g, b)
            ctx.move_to(pad + step * delta, midrule - half)
            ctx.line_to(pad + step * delta, midrule)
            ctx.stroke()
            
            # Draw bar lower half with semi-transparency
            ctx.set_source_rgba(r, g, b, 0.8)
            ctx.move_to(pad + step * delta, midrule)
            ctx.line_to(pad + step * delta, midrule + 0.9 * half)
            ctx.stroke()


    surface.write_to_png(str(out))


def interpole(x1: float, y1: float, x2: float, y2: float, x: float) -> float:
    """Linear interpolation between two points."""
    return y1 + (y2 - y1) * (x - x1) / (x2 - x1)


def visualize(
    audio: Path,
    tmp: Path,
    out: Path,
    seek: Optional[float] = None,
    duration: Optional[float] = None,
    rate: int = 60,
    bars: int = 50,
    speed: float = 4,
    time: float = 0.4,
    oversample: float = 3,
    fg_color: Tuple = (0.2, 0.2, 0.2),
    fg_color2: Tuple = (0.5, 0.3, 0.6),
    bg_color: Tuple = (1, 1, 1),
    bg_video: Optional[Path] = None,
    size: Tuple[int, int] = (400, 400),
    stereo: bool = False,
) -> None:
    """
    Generate waveform visualization video.
    
    Args:
        audio: Path to audio file
        tmp: Temporary directory for frames
        out: Output video file path
        seek: Start time in seconds
        duration: Duration in seconds
        rate: Video framerate
        bars: Number of bars in animation
        speed: Base speed of transitions
        time: Amount of audio shown at once
        oversample: Higher = more reactive
        fg_color: RGB foreground color (gradient start)
        fg_color2: RGB foreground color (gradient end)
        bg_color: RGB background color (used if no bg_video)
        bg_video: Path to background video file (optional)
        size: (width, height) output dimensions
        stereo: Whether to merge stereo channels (single waveform with richness)
    """
    try:
        wav, sr = read_audio(audio, seek=seek, duration=duration)
    except (IOError, ValueError) as err:
        fatal(err)
        raise

    # Prepare waveforms
    wavs = []
    if stereo:
        if wav.shape[0] != 2:
            fatal('stereo requires stereo audio file')
            raise ValueError('stereo requires stereo audio file')
        # Merge stereo channels into single waveform with richness
        merged = (wav[0] + wav[1]) / 2
        diff = np.abs(wav[0] - wav[1])
        merged = merged + 0.3 * diff
        wavs.append(merged)
    else:
        wav = wav.mean(0)
        wavs.append(wav)

    # Normalize
    for i in range(len(wavs)):
        if wavs[i].std() > 0:
            wavs[i] = wavs[i] / wavs[i].std()

    # Extract envelopes
    window = int(sr * time / bars)
    stride = int(window / oversample)
    envs = []
    for wav_ch in wavs:
        env = envelope(wav_ch, window, stride)
        env = np.pad(env, (bars // 2, 2 * bars))
        envs.append(env)

    total_duration = len(wavs[0]) / sr
    frames = int(rate * total_duration)
    smooth = np.hanning(bars)

    # Extract background video frames if provided
    bg_video_frames = []
    if bg_video and bg_video.exists():
        try:
            bg_video_frames = extract_video_frames(bg_video, tmp, rate, total_duration, size)
        except Exception as e:
            print(f"Warning: Failed to extract background video frames: {e}")
            print("Falling back to solid background color.")

    print("BG video path:", bg_video)
    print("BG frames extracted:", len(bg_video_frames))

    print("Generating the frames...")
    for idx in tqdm.tqdm(range(frames), unit=" frames", ncols=80):
        pos = (((idx / rate)) * sr) / stride / bars
        off = int(pos)
        loc = pos - off
        denvs = []
        
        for env in envs:
            env1 = env[off * bars:(off + 1) * bars]
            env2 = env[(off + 1) * bars:(off + 2) * bars]

            # Loud parts update faster
            maxvol = math.log10(1e-4 + env2.max()) * 10
            speedup = np.clip(interpole(-6, 0.5, 0, 2, maxvol), 0.5, 2)
            w = sigmoid(speed * speedup * (loc - 0.5))
            denv = (1 - w) * env1 + w * env2
            denv *= smooth
            denvs.append(denv)
        
        time_factor = idx / rate
        
        # Get corresponding background frame if available
        bg_frame = None
        if bg_video_frames:
            frame_idx = idx % len(bg_video_frames)
            bg_frame = bg_video_frames[frame_idx]
        
        intensity = max([env.max() for env in denvs])

        draw_env(
            denvs,
            tmp / f"{idx:06d}.png",
            (fg_color, fg_color2),
            bg_color,
            size,
            time_factor=time_factor,
            bg_video_frame=bg_frame,
            intensity=intensity
        )

    # Encode video
    audio_cmd = []
    if seek is not None:
        audio_cmd += ["-ss", str(seek)]
    audio_cmd += ["-i", str(audio.resolve())]
    if duration is not None:
        audio_cmd += ["-t", str(duration)]
    
    print("Encoding the animation video...")
    try:
        sp.run(
            [
                FFMPEG_PATH, "-y", "-loglevel", "error", "-r",
                str(rate), "-f", "image2", "-s", f"{size[0]}x{size[1]}", "-i", "%06d.png"
            ] + audio_cmd + [
                "-c:v", "libx264", "-crf", "10", "-pix_fmt", "yuv420p",
                "-c:a", "aac", "-b:a", "192k",
                "-map", "0", "-map", "1",
                str(out.resolve())
            ],
            check=True,
            cwd=str(tmp)
        )
        print(f"✓ Video generated successfully: {out}")
    except FileNotFoundError:
        raise IOError(f"ffmpeg not found at: {FFMPEG_PATH}\nPlease update FFMPEG_PATH in the script.")
    except sp.CalledProcessError as e:
        raise IOError(f"ffmpeg encoding failed. Error code: {e.returncode}")


def parse_color(colorstr: str) -> Tuple[float, float, float]:
    """Parse comma-separated RGB color string into tuple of floats."""
    try:
        r, g, b = [float(i) for i in colorstr.split(",")]
        return r, g, b
    except (ValueError, AttributeError):
        fatal("Format for color is 3 floats separated by commas 0.xx,0.xx,0.xx, rgb order")
        raise


def generate_waveform_video(
    audio_path: str,
    output_path: str,
    rate: int = 60,
    white_bg: bool = False,
    width: int = 480,
    height: int = 300,
    stereo: bool = False,
    bg_video: Optional[str] = None,
):
    """
    Generate waveform video from audio file.
    
    Args:
        audio_path: Path to input audio file
        output_path: Path to output video file
        rate: Video framerate (default: 60)
        white_bg: Use white background if True (default: False for black)
        width: Output video width in pixels (default: 480)
        height: Output video height in pixels (default: 300)
        stereo: Merge stereo channels if True (default: False)
        bg_video: Path to background video file (optional)
    
    Returns:
        Path to the generated video file
    """
    bg_video_path = None
    if bg_video:
        bg_video_path = Path(bg_video)
        if not bg_video_path.exists():
            print(f"Warning: Background video not found: {bg_video}")
            bg_video_path = None
    
    with tempfile.TemporaryDirectory() as tmp:
        visualize(
            Path(audio_path),
            Path(tmp),
            Path(output_path),
            rate=rate,
            fg_color=(0.03, 0.6, 0.3),
            fg_color2=(0.5, 0.3, 0.6),
            bg_color=(1, 1, 1) if white_bg else (0, 0, 0),
            bg_video=bg_video_path,
            size=(width, height),
            stereo=stereo,
        )

    return output_path


def main() -> None:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        'seewav', description="Generate a nice mp4 animation from an audio file.")
    parser.add_argument("-r", "--rate", type=int, default=60, help="Video framerate.")
    parser.add_argument("--stereo", action='store_true',
                        help="Merge stereo channels into single rich waveform.")
    parser.add_argument("-c", "--color",
                        default=[0.03, 0.6, 0.3],
                        type=parse_color,
                        dest="color",
                        help="Color of the bars as `r,g,b` in [0, 1] (gradient start).")
    parser.add_argument("-c2", "--color2",
                        default=[0.5, 0.3, 0.6],
                        type=parse_color,
                        dest="color2",
                        help="Color gradient end as `r,g,b` in [0, 1].")
    parser.add_argument("--white", action="store_true",
                        help="Use white background. Default is black.")
    parser.add_argument("--bg-video", type=str, default=None,
                        help="Path to background video file. If not provided, uses solid color background.")
    parser.add_argument("-B", "--bars", type=int, default=50,
                        help="Number of bars on the video at once")
    parser.add_argument("-O", "--oversample", type=float, default=4,
                        help="Lower values will feel less reactive.")
    parser.add_argument("-T", "--time", type=float, default=0.4,
                        help="Amount of audio shown at once on a frame.")
    parser.add_argument("-S", "--speed", type=float, default=4,
                        help="Higher values means faster transitions between frames.")
    parser.add_argument("-W", "--width", type=int, default=480,
                        help="width in pixels of the animation")
    parser.add_argument("-H", "--height", type=int, default=300,
                        help="height in pixels of the animation")
    parser.add_argument("-s", "--seek", type=float, help="Seek to time in seconds in video.")
    parser.add_argument("-d", "--duration", type=float, help="Duration in seconds from seek time.")
    parser.add_argument("audio", type=Path, help='Path to audio file')
    parser.add_argument("out",
                        type=Path,
                        nargs='?',
                        default=Path('out.mp4'),
                        help='Path to output file. Default is ./out.mp4')
    args = parser.parse_args()
    
    with tempfile.TemporaryDirectory() as tmp:
        visualize(
            args.audio,
            Path(tmp),
            args.out,
            seek=args.seek,
            duration=args.duration,
            rate=args.rate,
            bars=args.bars,
            speed=args.speed,
            oversample=args.oversample,
            time=args.time,
            fg_color=tuple(args.color),
            fg_color2=tuple(args.color2),
            bg_color=tuple([1. * bool(args.white)] * 3),
            bg_video=Path(args.bg_video) if args.bg_video else None,
            size=(args.width, args.height),
            stereo=args.stereo
        )


if __name__ == "__main__":
    _is_main = True
    main()



