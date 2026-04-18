from diffusers import StableDiffusionPipeline
import torch
import os
import sys
import json


# ================================
# LOAD MODEL (ONCE)
# ================================

def load_pipeline():
    pipe = StableDiffusionPipeline.from_pretrained(
        "runwayml/stable-diffusion-v1-5",
        torch_dtype=torch.float16
    ).to("cuda")

    pipe.enable_attention_slicing()
    pipe.enable_vae_slicing()

    return pipe


# ================================
# IMAGE GENERATION
# ================================

STYLE_SUFFIX = "anime style, vibrant colors, ubject centered, dark background, spotlight lighting"
NEGATIVE_PROMPT = "blurry, low quality, distorted face, bad anatomy, extra limbs"


def generate_images_from_scenes(scenes, output_dir):
    os.makedirs(output_dir, exist_ok=True)

    pipe = load_pipeline()

    image_paths = []

    for i, scene in enumerate(scenes):
        try:
            desc = scene["image_description"]
            prompt = f"{desc}, {STYLE_SUFFIX}"

            print(f"\n Generating image {i+1}/{len(scenes)}")
            print("Prompt:", prompt)

            image = pipe(
                prompt,
                negative_prompt=NEGATIVE_PROMPT,
                num_inference_steps=25,
                guidance_scale=7.5
            ).images[0]

            filename = os.path.join(output_dir, f"image{i+1}.png")
            image.save(filename)

            image_paths.append(filename)

            print(f" Saved: {filename}")

        except Exception as e:
            print(f" Error generating image {i}: {e}")

    print("\n All images generated!")

    return image_paths


# ================================
# MAIN (ENTRY FROM SUBPROCESS)
# ================================

if __name__ == "__main__":
    if len(sys.argv) < 2:
        raise ValueError("No JSON path provided")

    json_path = sys.argv[1]

    if not os.path.exists(json_path):
        raise FileNotFoundError(f"JSON not found: {json_path}")

    # Extract ID
    file_id = os.path.splitext(os.path.basename(json_path))[0]

    # Base project path
    base_dir = r"D:\CODE\Python\Projects\YTAuto"

    # Load scenes
    with open(json_path, "r") as f:
        scenes = json.load(f)

    # Output directory → data/shared/{id}/
    output_dir = os.path.join(base_dir, "data", "shared", file_id)

    # Generate images
    image_paths = generate_images_from_scenes(scenes, output_dir)

    # Save paths file (optional but useful)
    paths_file = os.path.join(output_dir, "paths.json")
    with open(paths_file, "w") as f:
        json.dump(image_paths, f, indent=2)

    print(f"\n Saved image paths → {paths_file}")

   
    try:
        os.remove(json_path)
        print(f" Deleted input JSON: {json_path}")
    except Exception as e:
        print(f" Failed to delete JSON: {e}")