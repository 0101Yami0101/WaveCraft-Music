import os
from acestep.generate_music import AceStepGenerator
from visuals.seewav_standalone import generate_waveform_video
from lrc.add_lrc import add_lyrics_to_video  # 👈 import your module
from bg_process.bg import generate_bg_video_and_details
from fg_process.logo_overlay import create_aura_logo_video
from fg_process.toenail import generate_thumbnail
from upload.upload_vid import upload_video

def init_pipeline():
    print("Pipeline initialized.")

    # Start Acestep

    # Generate Audio and Timestamps
    print("Starting Acestep..")
    request = "Aggressive Rap song with Hip-Hop music. Male and Female Vocals."

    generator = AceStepGenerator()
    generator.initialize("D:\\CODE\\Python\\Projects\\AceStep\\checkpoints")
    result = generator.generate_song(request)

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
    print("Final Step: Uploading..")
    upload_video(
        video_path=final_video_path,
        title=f"{song_name} | {genre} | WaveCraft Music ",
        description=description,
        tags=tags,
        thumbnail_path=thumbnail_path
    )

    print("✅ Pipeline executed successfully")
