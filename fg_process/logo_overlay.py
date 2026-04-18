import numpy as np
import scipy.signal as signal
from moviepy import VideoFileClip, ImageClip, CompositeVideoClip
import moviepy.video.fx as vfx

def create_aura_logo_video(video_path, logo_path, output_path="output_aura.mp4"):
    """
    Overlays two fixed logos: 
    - Top-Left: Aura beats smoothly to the music (bass/kicks).
    - Top-Right: Aura beats smoothly to the vocals.
    Ignores micro-noises to prevent jerky vibrations.
    """
    video = VideoFileClip(video_path)
    audio = video.audio
    
    if audio is None:
        raise ValueError("The video has no audio track.")

    # 1. EXTRACT AUDIO
    fps_analysis = 20 
    audio_fps = audio.fps if audio.fps else 44100
    audio_data = audio.to_soundarray(fps=audio_fps)
    
    # Convert stereo to mono
    if audio_data.ndim > 1:
        mono_audio = np.mean(audio_data, axis=1)
    else:
        mono_audio = audio_data

    nyquist = 0.5 * audio_fps
    
    # ---------------------------------------------------------
    # 2. AUDIO PROCESSING: MUSIC (LOW-PASS < 250 Hz)
    # ---------------------------------------------------------
    b_music, a_music = signal.butter(4, 250.0 / nyquist, btype='low', analog=False)
    music_audio = signal.filtfilt(b_music, a_music, mono_audio)

    # ---------------------------------------------------------
    # 3. AUDIO PROCESSING: VOCALS (BAND-PASS 300 - 3000 Hz)
    # ---------------------------------------------------------
    b_vocals, a_vocals = signal.butter(4, [300.0 / nyquist, 3000.0 / nyquist], btype='band', analog=False)
    vocals_audio = signal.filtfilt(b_vocals, a_vocals, mono_audio)

    # Function to calculate smoothed RMS volume from an audio array with a NOISE GATE
    def get_smoothed_volumes(filtered_audio_array):
        samples_per_frame = int(audio_fps / fps_analysis)
        num_frames = int(video.duration * fps_analysis)
        raw_vols = []
        
        for i in range(num_frames):
            start = i * samples_per_frame
            end = start + samples_per_frame
            chunk = filtered_audio_array[start:end]
            rms = np.sqrt(np.mean(chunk**2)) if len(chunk) > 0 else 0
            raw_vols.append(rms)
            
        # --- NEW: NOISE GATE ---
        # Calculate a threshold to ignore background noise and minor vibrations
        max_raw = max(raw_vols) if max(raw_vols) > 0 else 1
        mean_raw = np.mean(raw_vols)
        
        # The threshold is set to either the average volume or 20% of the max volume.
        # Only sounds louder than this will trigger an expansion.
        noise_threshold = max(mean_raw, max_raw * 0.20)
            
        smoothed_vols = []
        current_level = 0.0
        decay_rate = 0.85 # Keep at 0.85 for a smooth, wave-like fade
        
        for v in raw_vols:
            # If the sound is lower than our threshold, treat it as pure silence (0.0)
            active_v = v if v > noise_threshold else 0.0
            
            if active_v > current_level:
                # Big sound hits: expand instantly
                current_level = active_v
            else:
                # Silence or noise: fade away smoothly
                current_level = current_level * decay_rate
                
            smoothed_vols.append(current_level)
            
        return smoothed_vols

    volumes_music = get_smoothed_volumes(music_audio)
    volumes_vocals = get_smoothed_volumes(vocals_audio)

    max_vol_music = max(volumes_music) if max(volumes_music) > 0 else 1
    max_vol_vocals = max(volumes_vocals) if max(volumes_vocals) > 0 else 1

    # ---------------------------------------------------------
    # 4. BASE LOGOS & POSITION MATH
    # ---------------------------------------------------------
    logo_scale = 0.05 * 1.4 
    logo_base = ImageClip(logo_path).with_duration(video.duration).resized(logo_scale)
    
    video_w, video_h = video.size
    logo_w, logo_h = logo_base.size
    margin = 30  
    
    # Calculate Centers
    y_offset = 25
    center_x_left = margin + (logo_w / 2)
    center_y_left = margin + (logo_h / 2) + y_offset
    
    center_x_right = video_w - margin - (logo_w / 2)
    center_y_right = margin + (logo_h / 2) + y_offset

    # Pin the fixed logos
    logo_fixed_left = logo_base.with_position((center_x_left - logo_w / 2, center_y_left - logo_h / 2))
    logo_fixed_right = logo_base.with_position((center_x_right - logo_w / 2, center_y_right - logo_h / 2))

    # ---------------------------------------------------------
    # 5. DYNAMIC EFFECT GENERATORS
    # ---------------------------------------------------------
    def create_scale_func(volumes_list, max_v):
        def scale_func(t):
            idx = min(int(t * fps_analysis), len(volumes_list) - 1)
            vol_ratio = volumes_list[idx] / max_v
            return 1.0 + (vol_ratio * 0.4)
        return scale_func

    def create_opacity_func(volumes_list, max_v):
        def opacity_func(t):
            idx = min(int(t * fps_analysis), len(volumes_list) - 1)
            vol_ratio = volumes_list[idx] / max_v
            return vol_ratio * 0.7
        return opacity_func

    def apply_dynamic_opacity(clip, opacity_func):
        if clip.mask is not None:
            def filter_mask(get_frame, t):
                frame = get_frame(t)
                return (frame * opacity_func(t)).astype(frame.dtype)
            clip.mask = clip.mask.transform(filter_mask)
        return clip

    def create_pos_func(scale_func, cx, cy):
        def pos_func(t):
            scale = scale_func(t)
            return (cx - (logo_w * scale) / 2, cy - (logo_h * scale) / 2)
        return pos_func

    # ---------------------------------------------------------
    # 6. BUILD THE AURA LAYERS
    # ---------------------------------------------------------
    # A. MUSIC AURA (LEFT)
    scale_music = create_scale_func(volumes_music, max_vol_music)
    opacity_music = create_opacity_func(volumes_music, max_vol_music)
    
    aura_left = (logo_base
                 .with_effects([vfx.Resize(scale_music)]))
    aura_left = apply_dynamic_opacity(aura_left, opacity_music)
    aura_left = aura_left.with_position(create_pos_func(scale_music, center_x_left, center_y_left))

    # B. VOCAL AURA (RIGHT)
    scale_vocals = create_scale_func(volumes_vocals, max_vol_vocals)
    opacity_vocals = create_opacity_func(volumes_vocals, max_vol_vocals)
    
    aura_right = (logo_base
                  .with_effects([vfx.Resize(scale_vocals)]))
    aura_right = apply_dynamic_opacity(aura_right, opacity_vocals)
    aura_right = aura_right.with_position(create_pos_func(scale_vocals, center_x_right, center_y_right))

    # ---------------------------------------------------------
    # 7. COMPOSITE AND RENDER
    # ---------------------------------------------------------
    final_video = CompositeVideoClip([
        video, 
        aura_left, aura_right,         # Shadows go behind
        logo_fixed_left, logo_fixed_right # Fixed logos go on top
    ])
    
    final_video.write_videofile(output_path, codec="libx264", audio_codec="aac", fps=video.fps)
    
    video.close()
    final_video.close()
    
    return output_path