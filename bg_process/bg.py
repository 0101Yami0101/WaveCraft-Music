import subprocess
import time
import requests
import random
import ollama
import json
import shutil
import re
import os
from moviepy import ImageClip, concatenate_videoclips
from moviepy.video.fx import FadeIn, FadeOut
from bg_process.bg_blur import blur_video


def is_ollama_running():
    try:
        requests.get("http://localhost:11434")
        return True
    except:
        return False


def start_ollama_server():
    print("🚀 Starting Ollama server...")
    proc = subprocess.Popen(
        ["ollama", "serve"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )

    for _ in range(15):
        if is_ollama_running():
            print("✅ Ollama ready")
            return proc
        time.sleep(1)

    raise RuntimeError("❌ Failed to start Ollama")


def stop_ollama_server(force=True, timeout=5):
    """
    Fully stops Ollama server (kills all processes).
    
    Args:
        force (bool): If True, force kill using taskkill
        timeout (int): Seconds to wait before force kill
    """

    print("🛑 Stopping Ollama server...")

    # Step 1: Try graceful shutdown (optional)
    try:
        requests.post("http://localhost:11434/api/stop", timeout=2)
        print("⚡ Sent stop signal to Ollama API")
    except:
        pass

    # Step 2: Wait briefly to see if it stops
    for _ in range(timeout):
        try:
            requests.get("http://localhost:11434", timeout=1)
            time.sleep(1)
        except:
            print("✅ Ollama stopped gracefully")
            return

    # Step 3: Force kill (MAIN FIX)
    if force:
        print("💀 Force killing Ollama processes...")
        try:
            subprocess.run(
                ["taskkill", "/F", "/IM", "ollama.exe", "/T"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            print("✅ Ollama force killed")
        except Exception as e:
            print("❌ Failed to kill Ollama:", e)

    # Step 4: Final verification
    try:
        requests.get("http://localhost:11434", timeout=1)
        print("⚠️ Ollama still running (unexpected)")
    except:
        print("✅ Ollama fully stopped")


# ================================
# JSON CLEANER (IMPORTANT)
# ================================

def extract_total_duration_from_lrc(lrc_text):
    """
    Extract the total song duration from LRC text.
    Finds the last timestamp in the format [MM:SS.SS] or [MM:SS]
    """
    timestamps = re.findall(r"\[(\d{2}):(\d{2}(?:\.\d{2})?)\]", lrc_text)
    
    if not timestamps:
        raise ValueError("❌ No timestamps found in LRC text")
    
    # Get the last timestamp
    last = timestamps[-1]
    minutes = int(last[0])
    seconds = float(last[1])
    
    total_seconds = minutes * 60 + seconds
    
    # Round up to nearest integer and add a small buffer (1 second)
    return int(total_seconds) + 1


def format_time(seconds):
    """Convert seconds (float) to MM:SS format"""
    minutes = int(seconds) // 60
    secs = int(seconds) % 60
    return f"{minutes:02d}:{secs:02d}"


def extract_json(text):
    """
    Robust JSON extractor from messy LLM output
    """

    # Step 1: Try direct parse (fast path)
    try:
        return json.loads(text)
    except:
        pass

    # Step 2: Extract ALL possible JSON blocks
    candidates = re.findall(r"\{.*?\}|\[.*?\]", text, re.DOTALL)

    for candidate in candidates:
        try:
            return json.loads(candidate)
        except:
            continue

    # Step 3: Try fixing common issues
    cleaned = text.strip()

    # Remove markdown ```json blocks
    cleaned = re.sub(r"```.*?```", "", cleaned, flags=re.DOTALL)

    # Try again
    try:
        return json.loads(cleaned)
    except Exception as e:
        print("❌ JSON parse error:", e)

    raise ValueError("❌ Could not extract valid JSON from LLM output")
# ================================
# PROMPT GENERATION
# ================================

def generate_slideshow_plan(lrc_text, total_duration_seconds, model="mistral:7b-instruct"):
    # Format total duration as MM:SS
    total_duration_str = format_time(total_duration_seconds)
    
    prompt = f"""
You are a music video director. Your task is to create a COMPLETE slideshow plan that covers the ENTIRE song from start to finish.

CRITICAL: The song is EXACTLY {total_duration_str} seconds long ({total_duration_seconds} seconds). You MUST cover this entire duration.

Return ONLY valid JSON. No explanation. No text outside JSON.

Format EXACTLY like this:
[
  {{
    "time_start": "00:00",
    "time_end": "00:26",
    "image_description": "Detailed cinematic image description"
  }},
  {{
    "time_start": "00:26",
    "time_end": "00:52",
    "image_description": "Next detailed cinematic image description"
  }}
]

ABSOLUTE REQUIREMENTS:
- First image MUST start at "00:00"
- Last image MUST end at or after "{total_duration_str}" (the full song duration)
- NO GAPS between time_end of one image and time_start of next
- Continuous timeline coverage from 00:00 to {total_duration_str}
- Use MM:SS format (no decimals, no frames)
- 4-12 images total (NOT 10)
- Strict JSON only
- Double quotes only, no single quotes
- No trailing commas
- No comments, markdown, or text outside JSON

Instructions:
- Analyze the FULL lyrics provided
- Create cinematic slideshow scenes that match the song narrative
- Maintain consistent visual theme/style throughout
- Each scene should be 15-30 seconds typical duration
- Each description must be vivid, visual, and STANDALONE
- Descriptions examples: "Man walking on rain, city lights reflecting on wet pavement, moody atmosphere, cinematic lighting", "Woman sitting alone in a dimly lit room, soft light from window, introspective mood", "Couple dancing under neon lights, vibrant colors, energetic vibe"
- Each image is INDEPENDENT - don't reference other images, but connect them thematically
- Distribute scenes evenly across the {total_duration_str} duration

Lyrics with timestamps:
{lrc_text}
"""

    response = ollama.chat(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        keep_alive=0
    )

    raw = response["message"]["content"].strip()

    print("\n🧠 RAW LLM OUTPUT:\n", raw[:500], "...\n")  # debug

    return extract_json(raw)


def generate_details(lrc_text, request_prompt, model="mistral:7b-instruct"):
    """
    Generate comprehensive song details based on LRC text and request prompt.
    
    Args:
        lrc_text: The lyrics with timestamps
        request_prompt: The user's original song generation request
        model: Ollama model to use
    
    Returns:
        Dictionary with keys:
            - 'name': 1-3 word song title
            - 'description': Evocative description of the song
            - 'genre': Song genre
            - 'tags': List of 2-4 tags
    """
    prompt = f"""You are a music producer creating song metadata. Based on the user's request and the generated lyrics, create a JSON object with ONLY these fields:

USER REQUEST: {request_prompt}

Return ONLY valid JSON with this exact structure and no other text:
{{
  "name": "Song Title Here",
  "genre": "Genre",
  "tags": ["Tag1", "Tag2"],
  "description": "Song description here."
}}

Requirements:
- name: 1-3 word catchy song title
- genre: One music genre
- tags: 2-4 descriptive words in array
- description: 3-4 sentences about the song

SONG LYRICS:
{lrc_text}"""

    response = ollama.chat(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        keep_alive=0
    )

    raw = response["message"]["content"].strip()
    
    print(f"\n🧠 RAW DETAILS OUTPUT:\n{raw[:800]}\n")  # Debug output
    
    try:
        details = extract_json(raw)
        
        # Ensure all required fields exist
        required_fields = ['name', 'genre', 'tags', 'description']
        for field in required_fields:
            if field not in details:
                raise ValueError(f"Missing required field: {field}")
        
        print(f"\n🎵 Generated song details:")
        print(f"   Name: {details['name']}")
        print(f"   Genre: {details['genre']}")
        print(f"   Tags: {', '.join(details['tags'])}")
        print(f"   Description: {details['description'][:100]}...")
        
        return details
    
    except Exception as e:
        print(f"❌ Failed to parse song details: {e}")
        raise


def validate_and_fix_plan(plan, total_duration_seconds):
    """
    Validate that the plan covers the entire song duration.
    Fixes gaps, extends end time if needed, and adjusts durations.
    
    Returns: corrected plan
    """
    if not plan:
        raise ValueError("❌ Plan is empty")
    
    # Convert total duration to MM:SS
    total_duration_str = format_time(total_duration_seconds)
    
    # Check if first scene starts at 00:00
    if plan[0]["time_start"] != "00:00":
        print(f"⚠️ First scene doesn't start at 00:00, adjusting from {plan[0]['time_start']}")
        plan[0]["time_start"] = "00:00"
    
    # Check if last scene ends at or after total duration
    last_end_seconds = time_to_seconds(plan[-1]["time_end"])
    if last_end_seconds < total_duration_seconds:
        print(f"⚠️ Plan ends at {plan[-1]['time_end']} but song is {total_duration_str} long. Extending...")
        plan[-1]["time_end"] = total_duration_str
    
    # Validate no gaps between scenes
    for i in range(len(plan) - 1):
        current_end = plan[i]["time_end"]
        next_start = plan[i + 1]["time_start"]
        
        if current_end != next_start:
            print(f"⚠️ Gap found between scene {i} and {i+1}. Fixing: {current_end} -> {next_start}")
            plan[i + 1]["time_start"] = current_end
    
    # Log the corrected plan
    print(f"\n✅ Plan validated and corrected:")
    for i, scene in enumerate(plan):
        start = time_to_seconds(scene["time_start"])
        end = time_to_seconds(scene["time_end"])
        duration = end - start
        print(f"  Scene {i+1}: {scene['time_start']} -> {scene['time_end']} ({duration:.1f}s)")
    
    return plan


def generate_slideshow_from_lyrics(lrc_text, model="mistral:7b-instruct", manage_ollama=True):
    """
    Generate slideshow plan from LRC text.
    
    Args:
        lrc_text: The lyrics with timestamps
        model: Ollama model to use
        manage_ollama: If True, start/stop Ollama. If False, assume it's already running.
    
    Returns:
        List of scene dictionaries with timing and descriptions
    """
    proc = None

    # Extract total duration from LRC text
    total_duration_seconds = extract_total_duration_from_lrc(lrc_text)
    print(f"\n⏱️ Song duration: {format_time(total_duration_seconds)}")

    if manage_ollama:
        if not is_ollama_running():
            proc = start_ollama_server()
        else:
            print("⚡ Ollama already running")

    try:
        print("🎬 Generating slideshow plan...\n")
        result = generate_slideshow_plan(lrc_text, total_duration_seconds, model=model)
        
        # Validate and fix the plan
        result = validate_and_fix_plan(result, total_duration_seconds)
        
        return result

    finally:
        if manage_ollama:
            stop_ollama_server()



def time_to_seconds(t):
    try:
        parts = t.strip().split(":")
        if len(parts) != 2:
            raise ValueError(f"Invalid time format: {t}")

        minutes = int(parts[0])
        seconds = float(parts[1])

        return minutes * 60 + seconds

    except Exception as e:
        raise ValueError(f"❌ Failed to parse time '{t}': {e}")



def create_slideshow_video(plan, image_paths, output_path, fps=60):
    FFMPEG_PATH = r"D:\CODE\Python\Projects\YTAuto\ffmpeg\ffmpeg.exe"

    if len(plan) != len(image_paths):
        raise ValueError("❌ plan and image_paths length mismatch")

    print("🎬 Creating individual video clips from images...")

    temp_videos = []
    clip_durations = []

    # ================================
    # 1. CREATE CLIPS WITH EXACT DURATIONS FROM PLAN
    # ================================
    for i, scene in enumerate(plan):
        try:
            start = time_to_seconds(scene["time_start"])
            end = time_to_seconds(scene["time_end"])
            duration = max(0.1, end - start)
            clip_durations.append(duration)

            img = image_paths[i]
            img_dir = os.path.dirname(img)

            temp_video = os.path.join(img_dir, f"clip_{i}.mp4")

            print(f"  Clip {i+1}: {duration:.2f}s - {scene['image_description'][:50]}...")

            cmd = [
                FFMPEG_PATH,
                "-y",
                "-loop", "1",
                "-i", img,
                "-t", str(duration),
                "-vf", "scale=1920:1080:flags=lanczos",
                "-r", str(fps),
                "-pix_fmt", "yuv420p",
                "-c:v", "libx264",
                "-preset", "slow",
                "-crf", "18", 
                temp_video
            ]

            subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            temp_videos.append(temp_video)

        except Exception as e:
            print(f"❌ Error creating clip {i}: {e}")
            raise

    print(f"✅ Created {len(temp_videos)} clips")

    # ================================
    # 2. CREATE CONCAT FILE FOR PROPER SEQUENCING
    # ================================
    concat_file = os.path.join(os.path.dirname(temp_videos[0]), "concat_list.txt")
    
    with open(concat_file, "w") as f:
        for video in temp_videos:
            # Escape Windows backslashes for ffmpeg
            f.write(f"file '{video}'\n")
    
    print(f"✅ Concat file created with {len(temp_videos)} clips")

    # ================================
    # 3. CONCATENATE WITH TRANSITIONS
    # ================================
    print("✨ Concatenating clips with smooth transitions...")

    # Option: Use concat demuxer for pixel-perfect concatenation without timeline loss
    # Then add transitions if desired
    
    temp_concat = concat_file.replace(".txt", "_output.mp4")
    
    # Use concat demuxer for perfect timing
    cmd = [
        FFMPEG_PATH,
        "-y",
        "-f", "concat",
        "-safe", "0",
        "-i", concat_file,
        "-c", "copy",  # No re-encoding, just copy
        temp_concat
    ]
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print("❌ Concat failed:", result.stderr)
        raise RuntimeError("Failed to concatenate videos")
    
    print("✅ Clips concatenated without timeline loss")

    # ================================
    # 4. OPTIONAL: ADD TRANSITIONS BETWEEN CLIPS
    # ================================
    # NOTE: Transitions are visual effects only and should not affect timeline duration
    # Using fade-in/fade-out effects instead of overlapping xfade for perfect timing
    
    transitions = ["fade", "fadeleft", "faderight"]
    final_video = temp_concat
    
    # For now, skip transitions to preserve exact timing
    # If transitions are needed, they should be very short (0.3-0.5s) and not overlap
    
    # Verify the final output duration
    print("\n📊 Verifying video duration...")
    total_plan_duration = sum(clip_durations)
    print(f"   Total duration from plan: {total_plan_duration:.2f}s")
    
    # ================================
    # 5. FINAL OUTPUT
    # ================================
    os.replace(final_video, output_path)
    
    # Get actual file size for verification
    file_size_mb = os.path.getsize(output_path) / (1024 * 1024)
    print(f"\n🎉 Final video created: {output_path}")
    print(f"   File size: {file_size_mb:.1f} MB")
    print(f"   Expected duration: {format_time(int(total_plan_duration))} ({total_plan_duration:.2f}s)")

    # Cleanup temp files
    try:
        for video in temp_videos:
            if os.path.exists(video):
                os.remove(video)
        if os.path.exists(concat_file):
            os.remove(concat_file)
    except:
        pass

    return output_path

def cleanup_shared_folder(id):
    """
    Deletes the folder: data/shared/<id> safely
    """

    base_dir = r"D:\CODE\Python\Projects\YTAuto"
    shared_dir = os.path.join(base_dir, "data", "shared")
    target_dir = os.path.join(shared_dir, id)

    try:
        if not os.path.exists(target_dir):
            print(f"⚠️ Folder not found: {target_dir}")
            return

        # 🔒 safety check (VERY important)
        if not target_dir.startswith(shared_dir):
            raise Exception("❌ Unsafe delete blocked")

        shutil.rmtree(target_dir)

        print(f"🧹 Deleted folder: {target_dir}")

    except Exception as e:
        print(f"❌ Failed to delete folder {target_dir}: {e}")

def generate_bg_video_and_details(id, lrc_text, request_prompt):
    """
    Generate background video and comprehensive song details.
    
    Args:
        id: Unique identifier for the video
        lrc_text: Lyrics with timestamps
        request_prompt: User's original song generation request
    
    Returns:
        Dictionary with keys:
            - 'bg_video_path': Path to the final blurred background video
            - 'song_name': Generated 1-3 word song name
            - 'description': Evocative song description
            - 'genre': Song genre
            - 'tags': List of 2-4 descriptive tags
    """
    
    # ================================
    # OLLAMA SETUP (SINGLE LIFECYCLE)
    # ================================
    proc = None
    
    if not is_ollama_running():
        proc = start_ollama_server()
    else:
        print("⚡ Ollama already running")
    
    try:
        # 1. Generate plan (Ollama managed externally)
        print("\n📋 Starting plan and details generation with Ollama...\n")
        plan = generate_slideshow_from_lyrics(lrc_text, manage_ollama=False)
        
        # 2. Generate comprehensive song details (fresh prompt, Ollama still running)
        details = generate_details(lrc_text, request_prompt)
        
    finally:
        stop_ollama_server()

    # ================================
    # PROCEED WITH VIDEO GENERATION
    # ================================

    base_dir = r"D:\CODE\Python\Projects\YTAuto"
    shared_dir = os.path.join(base_dir, "data", "shared")
    os.makedirs(shared_dir, exist_ok=True)

    json_path = os.path.join(shared_dir, f"{id}.json")

    with open(json_path, "w") as f:
        json.dump(plan, f, indent=2)

    print(f"\n💾 Saved plan to: {json_path}")


    # CALL SD ENV (PYTHON 3.10)

    sd_python = r"D:\CODE\Python\Projects\YTAuto\sd_env\venv\Scripts\python.exe" #add to .env later
    sd_script = r"D:\CODE\Python\Projects\YTAuto\sd_env\generate_imgs.py" #add to .env later

    print("\n🚀 Running Stable Diffusion...\n")

    result = subprocess.run(
        [sd_python, sd_script, json_path],  
        capture_output=True,
        text=True
    )

    print("----- SD OUTPUT -----")
    print(result.stdout)

    if result.stderr:
        print("----- SD ERRORS -----")
        print(result.stderr)

    # ================================
    # 📸 READ GENERATED IMAGES
    # ================================

    images_dir = os.path.join(shared_dir, id)
    paths_file = os.path.join(images_dir, "paths.json")

    if not os.path.exists(paths_file):
        raise FileNotFoundError("❌ paths.json not found (SD may have failed)")

    with open(paths_file) as f:
        image_paths = json.load(f)

    print("\n📸 Images generated:", image_paths)

    # convert to slideshow video

    bg_video_path = os.path.join(shared_dir, f"{id}_bg.mp4")

    print("\n🎬 Creating slideshow video...\n")

    create_slideshow_video(
        plan=plan,
        image_paths=image_paths,
        output_path=bg_video_path
    )

    print(f"✅ Background video created: {bg_video_path}")
    
    # blur bg
    blurred_path = bg_video_path.replace(".mp4", "_blur.mp4")

    if os.path.exists(bg_video_path):
        blur_video(bg_video_path, blurred_path)

        # optionally remove original (clean)
        try:
            os.remove(bg_video_path)
        except:
            pass

        cleanup_shared_folder(id)

        return {
            'bg_video_path': blurred_path,
            'song_name': details['name'],
            'description': details['description'],
            'genre': details['genre'],
            'tags': details['tags']
        }

    else:
        print("❌ Video not created, skipping blur + cleanup")
        return {
            'bg_video_path': bg_video_path,
            'song_name': details['name'],
            'description': details['description'],
            'genre': details['genre'],
            'tags': details['tags']
        }
    

