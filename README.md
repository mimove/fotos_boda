# Ana & Miguel's wedding photos

A mobile-friendly wedding gallery. Guests can submit a selfie to find matching photos, and the organizer can choose public highlights. The app uses the photos in `files/`; it never modifies them. Selfies are used for matching and are not retained after processing. The web server may temporarily spool uploads to disk. Face recognition is approximate: it can miss photos or return another person, and group photos can include other guests. Get guests' consent before indexing or sharing their photos and tell them how the site works.

## Run locally

Requirements: Python 3.9 or newer, CMake, a C++ compiler, and internet access for the packages. On macOS, install Xcode Command Line Tools (`xcode-select --install`) and CMake (for example, `brew install cmake`). Building dlib, a face-recognition dependency, may take a while.

```sh
cd /Users/mimove/GitHub/fotos_boda
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export ADMIN_PASSWORD='choose-a-long-unique-password'
export APP_SECRET='choose-a-different-long-random-secret'
python index_photos.py
python app.py
```

Open http://127.0.0.1:5000. To choose public highlights, open http://127.0.0.1:5000/admin, enter any username and the `ADMIN_PASSWORD`, select photos, and save. By default, the public gallery includes the color and black-and-white collections, except color photos 48–129 and black-and-white photos 37–104. Those excluded files remain in face search. Gallery photos are grouped by breakfast, church, and banquet. The organizer page can further narrow the displayed selection. The index can take a long time for 1,116 photos; rerunning reuses entries for unchanged photos. Re-run after adding or changing photos. The index and selections are in `data/` and must be backed up privately. Do not commit photos or face data to a public repository.

On a phone, camera access requires HTTPS or localhost. The local server binds to this computer only. Use the phone's photo picker for initial testing after deployment, or configure HTTPS for a local network test.

## Deploy to a public URL

The included Dockerfile provides a starting point for a Linux server with Docker and a domain name. This is not yet a managed deployment: you need a server with enough storage for the photos, index, Docker build, and backups. Publish only with consent. The public gallery is visible to everyone, and anyone able to use the face search can obtain matching group photos. Signed image links expire after one hour but recipients can save or share images. The app has no guest authentication or rate limiting; add access controls and rate limiting at your reverse proxy before public use. Protect the administrator endpoint, and use HTTPS for all traffic.

1. Create a Linux server, install Docker and a reverse proxy such as Caddy, and point a domain's DNS record to the server. Allow ports 80 and 443 through the server firewall. Keep port 5000 private.
2. Securely transfer the app files, `files/`, and the locally generated `data/` directory to a private directory on the server. Keep their directory layout. Do not publish `data/` or `files/` as a static web directory.
3. In that directory, build and run the container. Set strong, different secrets in the shell without putting them in source control. Persist both mounted directories and keep `APP_SECRET` stable across restarts.

```sh
docker build -t wedding-photos .
read -rs ADMIN_PASSWORD; export ADMIN_PASSWORD; echo
read -rs APP_SECRET; export APP_SECRET; echo
docker run -d --name wedding-photos --restart unless-stopped \
  -p 127.0.0.1:5000:5000 \
  -e ADMIN_PASSWORD -e APP_SECRET \
  -v "$(pwd)/files:/photos:ro" -v "$(pwd)/data:/data" \
  wedding-photos
```

4. Configure Caddy for your domain, replacing `wedding.example.com` with your actual domain:

```caddyfile
wedding.example.com {
    reverse_proxy 127.0.0.1:5000
}
```

5. Start or reload Caddy. Once DNS and TLS are working, open `https://wedding.example.com`, test matching and organizer selection, then share that URL. See the [Caddy documentation](https://caddyserver.com/docs/) for installation and HTTPS setup.

To index on the server instead, run `docker exec wedding-photos python index_photos.py`. Back up `data/` and the original photos securely. Delete the container and sensitive backups when they are no longer needed.
