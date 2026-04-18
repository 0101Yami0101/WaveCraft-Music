import os
import pickle
import google_auth_oauthlib.flow
import googleapiclient.discovery
import googleapiclient.http

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]

# 📁 Get current file directory (upload/)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# 📁 Define paths inside upload folder
CLIENT_SECRETS_PATH = os.path.join(BASE_DIR, "client_secrets.json")
TOKEN_PATH = os.path.join(BASE_DIR, "token.pickle")


def authenticate_youtube():
    creds = None

    # ✅ Load existing token
    if os.path.exists(TOKEN_PATH):
        with open(TOKEN_PATH, "rb") as token:
            creds = pickle.load(token)

    # ❗ If no valid creds → login
    if not creds:
        flow = google_auth_oauthlib.flow.InstalledAppFlow.from_client_secrets_file(
            CLIENT_SECRETS_PATH, SCOPES
        )
        creds = flow.run_local_server(port=0)

        # ✅ Save token in upload folder
        with open(TOKEN_PATH, "wb") as token:
            pickle.dump(creds, token)

    return googleapiclient.discovery.build("youtube", "v3", credentials=creds)


def upload_video(video_path, title, description, tags, thumbnail_path):
    youtube = authenticate_youtube()

    request = youtube.videos().insert(
        part="snippet,status",
        body={
            "snippet": {
                "title": title,
                "description": description,
                "tags": tags,
                "categoryId": "10"  # Music
            },
            "status": {
                "privacyStatus": "public"  # change to private if testing
            }
        },
        media_body=googleapiclient.http.MediaFileUpload(
            video_path,
            chunksize=-1,
            resumable=True
        )
    )

    response = request.execute()
    video_id = response["id"]

    print("Uploaded Video ID:", video_id)

    # ✅ Upload thumbnail
    youtube.thumbnails().set(
        videoId=video_id,
        media_body=googleapiclient.http.MediaFileUpload(thumbnail_path)
    ).execute()

    print("Thumbnail uploaded.")

    return video_id


# Optional test run
if __name__ == "__main__":
    upload_video(
        video_path="test.mp4",
        title="Test Upload",
        description="Test Description",
        tags=["test"],
        thumbnail_path="thumb.png"
    )