# Local-network-utility

A simple private drop zone for **files and copy-paste text** that you host on your own computer.
Upload once, then open or download from your phone, tablet or another laptop — on the **same Wi-Fi/LAN**,
or from **a completely different network** (mobile data, another city) using **Tailscale**.

No cloud account, no file-size limits from a third-party service, and your files never leave your own machines.

---

## Table of contents

1. [What it does](#what-it-does)
2. [How it works](#how-it-works)
3. [Part 1 — Install Tailscale and connect your devices](#part-1--install-tailscale-and-connect-your-devices)
4. [Part 2 — Run the project](#part-2--run-the-project)
5. [Part 3 — Open it from other devices](#part-3--open-it-from-other-devices)
6. [Part 4 — Keep it running in the background](#part-4--keep-it-running-in-the-background)
7. [Using the website](#using-the-website)
8. [Settings](#settings)
9. [Updating](#updating)
10. [Security](#security)
11. [Troubleshooting](#troubleshooting)
12. [Contact](#contact)

---

## What it does

- **Upload files** (several at once) and **share text** (commands, links, notes).
- **Folders** (nested): choose the destination folder when uploading, or open a folder and upload inside it.
- **Move** items between folders, **rename** and **delete** folders.
- **Open files in the browser**: images (with thumbnails), video, audio, PDF and text/code files, with Prev/Next buttons (and the ← → keys).
- **Copy a link**, **download** or **delete** any item.
- Works on phones, tablets and desktops.

## How it works

The project is a small [Flask](https://flask.palletsprojects.com/) web server that runs on **your computer** (the "host").
Everything is stored next to the code:

| Path | Purpose |
|---|---|
| `uploads/` | The uploaded files (random file names) |
| `items.json` | List of files/texts and which folder each one is in |
| `folders.json` | The folder tree |

There are two ways to reach it from other devices:

```
 Same Wi-Fi / LAN                        Different network (anywhere)
 ────────────────                        ────────────────────────────
 phone ──► http://192.168.1.20:5000      phone ──► https://my-pc.tailXXXX.ts.net
            (host IP on the LAN)                    (Tailscale private network)
```

- **Same network:** open `http://<host-LAN-IP>:5000`. Simple, no extra software.
- **Different network:** use **Tailscale**. It creates an encrypted private network (a "tailnet") between *your own* devices, so the site is reachable from anywhere **but only by devices signed in to your account** — nothing is exposed to the public internet and no router port-forwarding is needed.

> If you only need the same Wi-Fi, you can skip Part 1.

---

## Part 1 — Install Tailscale and connect your devices

You need Tailscale on **the host computer** (the one that runs this project) **and on every device you want to open the site from**. All devices must sign in with the **same account**. Tailscale is free for personal use.

### 1. Create the account

Go to <https://login.tailscale.com> and sign in with Google, Microsoft, GitHub or Apple. This creates your tailnet.

### 2. Install on the host computer

**Arch Linux and Arch-based distros** (Manjaro, EndeavourOS, custom distros…):

```bash
sudo pacman -Syu tailscale
sudo systemctl enable --now tailscaled
```

**Debian / Ubuntu / Kali / Fedora / most other Linux:**

```bash
curl -fsSL https://tailscale.com/install.sh | sh
```

> The install script detects your distro from `/etc/os-release`. On a custom distro it may fail with
> *"Couldn't determine what kind of Linux is running"*. In that case install from your package manager instead
> (for Arch-based systems use the `pacman` commands above), or see <https://tailscale.com/download/linux>.

**macOS / Windows:** download the app from <https://tailscale.com/download>, install it and sign in.

### 3. Sign in on the host

```bash
sudo tailscale up
```

It prints a login link. Open it in a browser, sign in, and press **Connect**.
**Keep the terminal open until it prints `Success.`** — closing it early leaves the device logged out.

Check:

```bash
tailscale status      # should list your devices, not "Logged out"
tailscale ip -4       # your Tailscale address, e.g. 100.x.y.z
```

### 4. Install on your other devices (phone, tablet, laptop)

- **Android:** Google Play → *Tailscale*
- **iPhone / iPad:** App Store → *Tailscale*
- **Windows / macOS / Linux:** same installers as above

Open the app and **sign in with the same account**. The device appears in the admin console under **Machines**: <https://login.tailscale.com/admin/machines>. Make sure the toggle in the app is **on / Connected**.

### 5. Enable MagicDNS and HTTPS (one time)

In the admin console open **DNS** and turn on **MagicDNS** and **Enable HTTPS**.
This gives your host a name such as `my-pc.tailXXXX.ts.net` and a real HTTPS certificate.

Test the connection from another device:

```bash
tailscale ping my-pc
```

---

## Part 2 — Run the project

Requirements: **Python 3.9+** and **git**.

```bash
git clone https://github.com/imrnsec/Local-network-utility.git
cd Local-network-utility

python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt

HOST=127.0.0.1 python app.py       # Windows PowerShell: $env:HOST="127.0.0.1"; python app.py
```

Open <http://127.0.0.1:5000> on the host computer. You should see the upload page.

Which `HOST` should I use?

| Goal | Run with |
|---|---|
| Only through Tailscale (recommended) | `HOST=127.0.0.1` |
| Also from the same Wi-Fi/LAN | `HOST=0.0.0.0` (the default) |

---

## Part 3 — Open it from other devices

### A) Same Wi-Fi / LAN

Start the app with `HOST=0.0.0.0 python app.py`, find the host's LAN address and open it on the other device:

```bash
hostname -I            # e.g. 192.168.1.20
```

`http://192.168.1.20:5000`

If it does not load, allow TCP port 5000 in the host firewall — only for your trusted local network.

### B) Different network, using Tailscale (recommended)

Keep the app on `127.0.0.1` and let Tailscale publish it **to your tailnet only**:

```bash
sudo tailscale serve --bg 5000
tailscale serve status
```

The output shows your address, for example:

```
https://my-pc.tailXXXX.ts.net  (tailnet only)
|-- / proxy http://127.0.0.1:5000
```

Open that address on any device signed in to your Tailscale account — on any network, including mobile data.

Stop publishing:

```bash
sudo tailscale serve --https=443 off
```

Alternative without HTTPS: run the app with `HOST=$(tailscale ip -4) python app.py` and open `http://100.x.y.z:5000`.

> ⚠️ **Never use `tailscale funnel` with this project.** Funnel puts the site on the public internet, and the app has no login.

---

## Part 4 — Keep it running in the background

Closing the terminal stops `python app.py`. To run it permanently on Linux, use a **systemd user service**.

Create `~/.config/systemd/user/lan-share.service` (create the folder first with `mkdir -p ~/.config/systemd/user`):

```ini
[Unit]
Description=LAN Share
After=network.target

[Service]
WorkingDirectory=%h/Local-network-utility
Environment=HOST=127.0.0.1
Environment=PORT=5000
ExecStart=%h/Local-network-utility/.venv/bin/python app.py
Restart=on-failure

[Install]
WantedBy=default.target
```

Change the two paths to where you cloned the project (`%h` means your home folder). Then:

```bash
systemctl --user daemon-reload
systemctl --user enable --now lan-share
loginctl enable-linger $USER        # start at boot even before you log in
systemctl --user status lan-share
```

Useful commands:

```bash
systemctl --user restart lan-share
journalctl --user -u lan-share -f
```

Make sure Tailscale also starts at boot: `sudo systemctl enable --now tailscaled`.
The `tailscale serve --bg` setting is remembered.

---

## Using the website

- **Upload:** pick the folder in **Save in folder**, choose files, press **Upload files**.
- **Share text:** paste text, optionally add a title, press **Save text**. Open it from another device and press **Copy text**.
- **Folders:** type a name and press **Create folder**. Click a folder to enter it; the breadcrumb at the top (`Home / Photos / Trips`) takes you back. Inside a folder you can rename or delete it (deleting removes everything inside it).
- **Open a file:** press **Open** (or click an image thumbnail). Use **‹ Prev / Next ›** to move through the folder.
- **Move an item:** use the **Move to…** menu next to it.
- **Download / Copy link / Delete:** the buttons on each row.

Files that the browser cannot show (zip, docx, …) are download-only.

## Settings

Environment variables:

| Variable | Default | Meaning |
|---|---|---|
| `HOST` | `0.0.0.0` | Interface to listen on (`127.0.0.1` = this computer only) |
| `PORT` | `5000` | Port |
| `MAX_UPLOAD_MB` | `512` | Maximum size of one upload request |
| `SECRET_KEY` | random | Flask session key |

Example: `MAX_UPLOAD_MB=2048 HOST=127.0.0.1 python app.py`

## Updating

```bash
cd Local-network-utility
git pull
systemctl --user restart lan-share      # if you use the service
```

Your uploads, `items.json`, `folders.json` and `.venv` are git-ignored, so updating never touches them.
**Do not delete the project folder to update it** — you would lose your `.venv` and uploaded files.

## Security

- The app has **no login**. Anyone who can open the site can view, upload and delete items.
  Use it only on a network you trust, or through Tailscale where only your own devices can reach it.
- Do not port-forward it on your router and do not use `tailscale funnel`.
- If you share your tailnet with other people, limit access with Tailscale **Access Controls**.
- HTML and SVG uploads are never displayed by the site (download-only), so an uploaded file cannot run code in your browser.
- Folders are virtual: folder names are never used as file system paths.
- Traffic through Tailscale is encrypted end to end. On plain LAN (`http://`) it is not encrypted.

## Troubleshooting

| Problem | Fix |
|---|---|
| `ModuleNotFoundError: No module named 'flask'` | Activate the virtualenv and run `pip install -r requirements.txt` |
| Tailscale install script: *Couldn't determine what kind of Linux* | Install with your package manager (`sudo pacman -S tailscale` on Arch-based systems) |
| `tailscale status` shows *Logged out* | Run `sudo tailscale up`, open the link, press **Connect**, and keep the terminal open until `Success.` |
| **502 Bad Gateway** on the `ts.net` address | Tailscale works but the app is not running on `127.0.0.1:5000`. Start it, or `systemctl --user status lan-share` |
| Service fails with `status=203/EXEC` | The path in `ExecStart` is wrong or `.venv` does not exist. Create it: `python -m venv .venv && .venv/bin/pip install -r requirements.txt` |
| `Address already in use` | Another copy is running. Stop it (`Ctrl+C`) or change `PORT` |
| Works on the host but not on other devices after a reboot | Check `systemctl is-enabled tailscaled`, `tailscale status`, `tailscale serve status`, and that the other device shows *Connected* in the Tailscale app |
| HTTPS address does not work | Enable **MagicDNS** and **HTTPS** in the Tailscale admin console → DNS |
| Upload rejected as too large | Raise `MAX_UPLOAD_MB` |

## Contact

Made by **imrnsec**.

- Instagram: [@imrn.sec](https://www.instagram.com/imrn.sec)
- X (Twitter): [@imrnsec](https://x.com/imrnsec)
- GitHub: [imrnsec](https://github.com/imrnsec)
