# drive-to-youtube

Upload a video from Google Drive (or a local file) to YouTube from the
command line. Resumable upload with retries, metadata, thumbnail, playlist,
and scheduling.

## What it does

- Finds a video in Google Drive by file id or exact name, and downloads it.
- Uploads it to YouTube with a resumable upload that retries server errors.
- Sets title, description, tags, category, language, privacy, publish time,
  thumbnail, and playlist.
- Reads the video back after upload and prints its watch URL.
- Defaults to `unlisted`, so nothing goes public by accident.

## Setup

You need a Google Cloud project with an OAuth client. This is a one-time
setup, about five minutes in the Google Cloud Console.

1. Create a project at [Google Cloud Console](https://console.cloud.google.com/).
2. Enable two APIs in that project: **Google Drive API** and
   **YouTube Data API v3**.
3. Go to **APIs & Services > Credentials > Create Credentials > OAuth client
   ID**, pick **Desktop app**, and download the JSON.
4. Save it as `~/.config/drive2yt/client_secret.json`.
5. Install the tool and sign in:

```bash
pip install drive2yt
drive2yt auth
```

`drive2yt auth` opens Google sign-in in your browser. Sign in with the
Google account that owns the YouTube channel you want to upload to.
Uploads always go to the signed-in account's channel. The token is stored
at `~/.config/drive2yt/token.json` and refreshed automatically.

### Quota

The YouTube Data API gives a fresh project 10,000 quota units a day. One
video upload costs about 1,600 units, so that covers about 6 uploads a day.
Request a quota increase in Google Cloud if you need more.

## Usage

```bash
# Upload a video from Drive by name
drive2yt upload --drive-name "Kyoto Temple Rain.mp4" \
  --title "Kyoto Temple Rain | Engawa Lofi" \
  --description "Rain on a Kyoto temple roof. 50 minutes of calm." \
  --tags "lofi,kyoto,rain sounds" \
  --privacy unlisted

# Upload a Drive file by id, schedule it, set a thumbnail and playlist
drive2yt upload --drive-id 1AbC2dEfGhIjKlMnOpQrStUv \
  --title "My video" --privacy private \
  --publish-at 2026-11-15T14:00:00Z \
  --thumbnail ./thumb.jpg --playlist PLxxxxxxxxxxxxxxxx

# Upload a local file instead
drive2yt upload --file ./clip.mp4 --title "My video" --privacy public

# Look up a Drive file without uploading
drive2yt find --drive-name "Kyoto Temple Rain.mp4"

# Check the metadata without uploading
drive2yt upload --drive-name "clip.mp4" --title "Test" --dry-run
```

Common category ids: 22 People & Blogs, 27 Education, 28 Science &
Technology, 10 Music, 24 Entertainment, 26 Howto & Style.

A scheduled upload needs `--privacy private` plus `--publish-at`.
YouTube flips it public at publish time. The publish time must be in the
future and in ISO 8601 form, for example `2026-11-15T14:00:00Z`.

## How uploads work

The upload uses YouTube's resumable upload protocol in 8 MB chunks. On a
500, 502, 503, or 504 error, or a dropped connection, it waits with
exponential backoff and retries, up to 10 times. The Drive download is
also chunked. A downloaded file is deleted after a successful upload
unless you pass `--keep-download`.

## Development

```bash
git clone https://github.com/richardsondx/drive-to-youtube
cd drive-to-youtube
pip install -e ".[dev]"
pytest
```

No live Google credentials are needed for the tests; the YouTube calls are
mocked.

## License

MIT. See [LICENSE](LICENSE).
