import os

# ✅ MUST be before importing or using Client
os.environ["GRADIO_TEMP_DIR"] = "./temp"

from gradio_client import Client


class AceStepGenerator:
    def __init__(self, base_url="http://127.0.0.1:7860/"):
        self.client = Client(base_url)
        self.initialized = False

    # ✅ 1. Initialize model (call ONCE)
    def initialize(self, checkpoint_path):
        if self.initialized:
            print("Model already initialized. Skipping...")
            return

        print("Initializing model...")

        init = self.client.predict(
            checkpoint_path,
            "acestep-v15-turbo",
            "cuda",
            True,
            "acestep-5Hz-lm-0.6B",
            "pt",
            False,
            True, True, True, True, False,
            "Custom",
            1,
            api_name="/lambda_3"
        )

        self.initialized = True
        print("Init complete:", init)

    # ✅ 2. Generate metadata (caption, lyrics, etc.)
    def generate_metadata(self, query):
        print("Generating metadata...")

        result = self.client.predict(
            query=query,
            instrumental=False,
            vocal_lang="en",
            temp=0.85,
            top_k=0,
            top_p=0.9,
            debug=False,
            api_name="/lambda_23"
        )

        metadata = {
            "caption": result[0],
            "lyrics": result[1].replace("\\n", "\n"),
            "bpm": result[2],
            "duration": result[3],
            "key": result[4],
            "vocal_language": result[5],
            "time_signature": result[7],
            "instrumental": result[8],
            "think": result[9],
            "status": result[10],
            "mode": result[11]
        }

        print("Metadata generated.")
        return metadata

    # ✅ 3. Generate audio and return file path
    def generate_audio(self, metadata):
        print("Generating audio...")

        result = self.client.predict(
            param_0=metadata["caption"],
            param_1=metadata["lyrics"],
            param_2=metadata["bpm"],
            param_3=metadata["key"],
            param_4=metadata["time_signature"],
            param_5=metadata["vocal_language"],
            param_6=8,
            param_7=7,
            param_8=True,
            param_9="-1",
            param_10=None,
            param_11=metadata["duration"],
            param_12=1,
            param_13=None,
            param_14="",
            param_15=0,
            param_16=-1,
            param_17="Fill the audio semantic mask based on the given conditions:",
            param_18=1,
            param_19=0,
            param_20="text2music",
            param_21=False,
            param_22=0,
            param_23=1,
            param_24=3,
            param_25="ode",
            param_26="",
            param_27="mp3",
            param_28=0.85,
            param_29=metadata["think"],
            param_30=2,
            param_31=0,
            param_32=0.9,
            param_33="NO USER INPUT",
            param_34=True,
            param_35=False,
            param_36=True,
            param_38=False,
            param_39=True,
            param_40=False,
            param_41=True,
            param_42=0.5,
            param_43=8,
            param_44="vocals",
            param_45=["vocals"],
            param_46=True,
            param_47=-1,
            param_48=0,
            param_49=0,
            param_50=0,
            param_51=1,
            param_52="balanced",
            param_53=0.5,
            param_54=False,
            api_name="/generation_wrapper"
        )

        # ✅ Extract audio path
        try:
            audio_path = result[0]["value"]
        except Exception:
            audio_path = result[8][0]

        # ✅ Extract timestamped lyrics (AutoLRC output)
        timestamps = None
        try:
            timestamps = result[28]["value"]  # THIS is what you want
        except Exception:
            print("No timestamps found.")

        print("Audio generated:", audio_path)
        print("Timestamps extracted.")

        return {
            "audio_path": audio_path,
            "timestamps": timestamps
        }

    # ✅ 4. Full pipeline (optional helper)
    def generate_song(self, query):
        metadata = self.generate_metadata(query)
        result = self.generate_audio(metadata)
        return result