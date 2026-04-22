import os
from acestep.generate_music import AceStepGenerator
from visuals.seewav_standalone import generate_waveform_video
from lrc.add_lrc import add_lyrics_to_video  # 👈 import your module
from bg_process.bg import generate_bg_video_and_details
from fg_process.logo_overlay import create_aura_logo_video
from fg_process.toenail import generate_thumbnail
from upload.upload_vid import upload_video
from acestep.acestep_manager import start_acestep, stop_acestep, is_acestep_running

def init_pipeline():
    request = "A Rock/electronic rock track with a deeply emotional and melancholic tone, carrying an introspective yet slightly aggressive energy. It moves at a moderate tempo, roughly around 105 to 115 BPM, set in a minor key that reinforces its somber atmosphere. The song opens with a soft, ambient intro driven by synth pads and delicate piano notes, gradually easing into a restrained first verse with clean guitar textures and vulnerable vocals. As it progresses, tension builds through layered synths and subtle percussion, leading into a powerful, cathartic chorus where distorted guitars, full drums, and intense vocal delivery take over. The second verse expands on this foundation with added depth, while an atmospheric bridge introduces echoing vocals and electronic elements that heighten the emotional weight. The final chorus reaches peak intensity with layered harmonies, before the track fades out into a reflective outro carried by piano or synth. Throughout, the instrumentation blends clean and distorted guitars, punchy drums, and ambient electronic textures, supporting dynamic male vocals that shift from soft and fragile to powerful and expressive. Lyrically and emotionally, the song explores inner conflict, identity struggles, overwhelming pressure, and the longing to break free from expectations, all wrapped in a polished yet slightly gritty production style."

    print("Pipeline initialized.")

    # Generate Audio and Timestamps
    acestep_proc = None
    try:
        if not is_acestep_running():
            acestep_proc = start_acestep()
        else:
            print("⚡ AceStep already running")

        generator = AceStepGenerator()
        generator.initialize("D:\\CODE\\Python\\Projects\\AceStep\\checkpoints")

        result = generator.generate_song(request)

    finally:
        if acestep_proc:
            stop_acestep(acestep_proc)


    # Extract audio path and timestamps
    print("Extracting audio and timestamps from result..")
    audio_path = result["audio_path"] # Delete the folder of this file after pipeline is done, to save space
    timestamped_lyrics = result["timestamps"] 
    filename = os.path.basename(audio_path)
    id = os.path.splitext(filename)[0]

    # Stop Acestep
    print("Stopping Acestep..")

    # Generate Background Video and Video Details
    print("Starting BG and Details processes..")
    bg_process_result = generate_bg_video_and_details(id, timestamped_lyrics, request)
    bg_video_path = bg_process_result['bg_video_path']
    song_name = bg_process_result['song_name']
    description = bg_process_result['description']
    genre = bg_process_result['genre']
    tags = bg_process_result['tags']


    # Generate Waveform
    print(f"Generating Waveform for {id}")
    wave_video_path = generate_waveform_video(
        audio_path=audio_path,
        output_path=f"D:\\CODE\\Python\\Projects\\YTAuto\\data\\temp\\{id}_visualiser.mp4",
        rate=60,
        white_bg=False,
        width=960, 
        height=600,
        stereo=True,
        bg_video=bg_video_path
    )

    # Add logo overlay to Waveform video
    print(f"Adding Logo overlay..")
    logo_path = "D:\\CODE\\Python\\Projects\\YTAuto\\assets\\logo.png"
    afterlogo_video_path = create_aura_logo_video(wave_video_path, logo_path, f"D:\\CODE\\Python\\Projects\\YTAuto\\data\\temp\\{id}_visualiser+logo.mp4" )


    # Add lyrics after Logo
    print("Adding Lyrics..")
    final_video_path = add_lyrics_to_video(
        video_path=afterlogo_video_path,
        lrc_text=timestamped_lyrics
    )

    # Create Thumbnail
    print("Creating Thumbnail")
    thumbnail_path = generate_thumbnail(id= id, title_text=song_name)

    # Upload 
    tags_str = " ".join(f"#{tags}" for tag in tags)
    description_full = f"""
    {description}

    .
    .

    Dive into the sound of emotion, rhythm, and atmosphere with WaveCraft Music.

    From late-night drives to quiet moments of reflection, every track is crafted to take you somewhere else.

    Let the music carry you — whether you're chasing memories, creating new ones, or just vibing in the moment.

    🔔 Subscribe for new music regularly
    🎧 Turn up the volume and feel the wave
    {tags_str}
    
    """
    
    print("Final Step: Uploading..")
    upload_video(
        video_path=final_video_path,
        title=f"{song_name} | {genre} | WaveCraft Music ",
        description=description,
        tags=tags,
        thumbnail_path=thumbnail_path
    )

    print("✅ Pipeline executed successfully")
