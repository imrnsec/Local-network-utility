# Local-network-utility
A simple private drop zone for files and copy-paste text on your local network. Upload once, then open or download from another device.

## Features

- Upload files and share text snippets
- Folders (nested): choose the destination when uploading, or open a folder and upload inside it
- Move items between folders, rename and delete folders
- Open images, video, audio, PDF and text files directly in the browser (with Prev/Next)
- Copy links, download, delete

## Run

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
HOST=127.0.0.1 python app.py
```

Open http://127.0.0.1:5000

## Use from other devices with Tailscale

Keep the app on `127.0.0.1` and let Tailscale expose it to your own devices only:

```bash
sudo tailscale serve --bg 5000
tailscale serve status
```

Open the `https://<machine>.<tailnet>.ts.net` address shown on any device signed in to your tailnet.
Do not use `tailscale funnel`: the app has no login and would be public.

## Run in the background (systemd user service)

`~/.config/systemd/user/lan-share.service`:

```ini
[Unit]
Description=LAN Share
After=network.target

[Service]
WorkingDirectory=%h/Downloads/lan-share
Environment=HOST=127.0.0.1
Environment=PORT=5000
ExecStart=%h/Downloads/lan-share/.venv/bin/python app.py
Restart=on-failure

[Install]
WantedBy=default.target
```

```bash
systemctl --user daemon-reload
systemctl --user enable --now lan-share
loginctl enable-linger $USER
```

Adjust the paths to where you cloned the project.

## Settings

| Variable | Default | Meaning |
|---|---|---|
| `HOST` | `0.0.0.0` | Interface to listen on (`127.0.0.1` = this computer only) |
| `PORT` | `5000` | Port |
| `MAX_UPLOAD_MB` | `512` | Max size per upload request |
| `SECRET_KEY` | random | Flask session key |

## Notes

- Files are stored in `uploads/`; metadata in `items.json` and `folders.json`. These are git-ignored.
- Folders are virtual: files stay flat in `uploads/` with random names.
- HTML and SVG uploads are download-only (never rendered by the site).
- No login: anyone who can reach the site can add, view and delete items. Use only on a trusted network or tailnet.
