# Ana & Miguel's wedding photos

A mobile-friendly wedding gallery. Guests can submit a selfie to find matching photos, and the organizer can choose public highlights. The app uses the photos in `files/`; it never modifies them. Selfies are used for matching and are not retained after processing. The web server may temporarily spool uploads to disk. Face recognition is approximate: it can miss photos or return another person, and group photos can include other guests. Get guests' consent before indexing or sharing their photos and tell them how the site works.

## Run locally

Requirements: Python 3.13, CMake, a C++ compiler, and internet access for the packages. On macOS, install Xcode Command Line Tools (`xcode-select --install`) and CMake (for example, `brew install cmake libpng`). Building dlib, a face-recognition dependency, may take a while.

If `.venv` was created with an older Python version, rename or remove it before creating the Python 3.13 environment.

```sh
cd /Users/mimove/GitHub/fotos_boda
python3.13 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export ADMIN_PASSWORD='choose-a-long-unique-password'
export APP_SECRET='choose-a-different-long-random-secret'
export GUEST_PASSWORD='choose-a-random-guest-password'
python index_photos.py
python app.py
```

Open http://127.0.0.1:5000. To choose public highlights, open http://127.0.0.1:5000/admin, enter any username and the `ADMIN_PASSWORD`, select photos, and save. By default, the gallery includes the color and black-and-white collections, except color photos 48–129 and black-and-white photos 37–104. Face search uses only photos currently shown in the gallery, including any changes made in the organizer page. Gallery photos are grouped by breakfast, church, and banquet. The index can take a long time for 1,116 photos; rerunning reuses entries for unchanged photos. Re-run after adding or changing photos. The index and selections are in `data/` and must be backed up privately. Do not commit photos or face data to a public repository.

On a phone, camera access requires HTTPS or localhost. The local server binds to this computer only. Use the phone's photo picker for initial testing after deployment, or configure HTTPS for a local network test.

## Deploy behind Cloudflare Tunnel

Run `docker compose up -d --build` on the VM. The app is available only on `127.0.0.1:5000`; never publish its port to the LAN or the internet. Keep the `files/` and `data/` directories private and back them up, along with `.env`. `files/` is mounted read-only; `data/` stores the face index and gallery selection. The container runs as UID 1000, which must be able to read the photos and write to `data/`. Compose sets `OPENBLAS_CORETYPE=CORE2` for compatibility with generic virtual CPUs and limits OpenBLAS to one thread.

Create `.env` with restrictive permissions and independent random secrets. Keep `APP_SECRET` stable across restarts:

```sh
umask 077
printf 'APP_SECRET=%s\nADMIN_PASSWORD=%s\nGUEST_PASSWORD=%s\n' "$(openssl rand -hex 32)" "$(openssl rand -hex 24)" "$(openssl rand -hex 6)" > .env
```

Do this only when `.env` does not already exist. Share `GUEST_PASSWORD` with guests; the gallery and photo URLs require it. The application fails closed if it is missing and limits repeated login failures. Changing it invalidates guest sessions after the container is recreated. Open the administrator page at `/admin` using any username and `ADMIN_PASSWORD`, after guest login. To rebuild the face index after adding photos, run `docker compose exec wedding python index_photos.py`. Maintain backups of the original media, the index and selection. Rebuild the image periodically to install container security updates.

Set up a Cloudflare Tunnel public hostname targeting `http://127.0.0.1:5000`. Protect both `/admin` and `/api/admin/photos` with Cloudflare Access and rate-limit face matching and login before publishing. Purge previously cached public content after enabling the password wall, and ensure Cloudflare cache rules do not override the app's private no-store headers. Face recognition can reveal other people in group photos and is not an identity check. Publish only with guests' consent. See the [Cloudflare Tunnel setup guide](https://developers.cloudflare.com/tunnel/get-started/).

### Automatic updates

The VM runs a user systemd timer that checks GitHub's `main` branch about once per minute using its read-only deploy key. When the commit changes, it builds and starts Compose from `~/apps/fotos_boda-auto`, a separate checkout. That checkout links to the existing `.env`, `files/`, and `data/` in `~/apps/fotos_boda`. It never copies these into Git or replaces them. Only fast-forward updates are deployed; a failed build is retried on the next check. The updater waits until a commit with `docker-compose.yml` is present on `main`.

To enable the timer on another VM, install `deploy/auto-deploy.sh` as `~/.local/bin/wedding-auto-deploy`, copy the two unit files from `deploy/` to `~/.config/systemd/user/`, run `systemctl --user daemon-reload` and `systemctl --user enable --now wedding-auto-deploy.timer`, and enable user lingering with `loginctl enable-linger "$USER"`. The VM must have Docker, the GitHub deploy key and persistent directories configured first.

Check updates with `systemctl --user status wedding-auto-deploy.timer` and `journalctl --user -u wedding-auto-deploy.service -n 50 --no-pager`. Push only reviewed changes to `main`: they are deployed automatically. Container rebuilds can briefly interrupt the site.
