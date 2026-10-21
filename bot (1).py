import os, re, sys, time, datetime, subprocess, urllib.parse, requests
from PIL import Image, ImageDraw, ImageFont, ImageFilter

SITE = "prompt-u33v.onrender.com"
KEY = os.getenv("POLLINATIONS_KEY", "")
UID = os.getenv("IG_USER_ID", "")
TOKEN = os.getenv("IG_TOKEN", "")
TEST = os.getenv("TEST_FALLBACK") == "1"

# 1. pick today's prompt from the website file
html = open("index.html", encoding="utf8").read()
rows = re.search(r"const D=`(.*?)`", html, re.S).group(1).strip().split("\n")
day = (datetime.date.today() - datetime.date(2026, 1, 1)).days
cat, title, prompt = rows[day % len(rows)].split("|")
print("Today:", title)

# 2. make the picture
def get_image():
    if TEST:
        return Image.new("RGB", (1024, 1280), (120, 60, 200))
    print("Key set:", bool(KEY))
    base = "https://gen.pollinations.ai/image/" + urllib.parse.quote(prompt + ", ultra detailed, sharp focus")
    q = f"?width=1024&height=1280&nologo=true&seed={day}"
    tries = [(base + q + (f"&key={KEY}" if KEY else ""), {}),
             (base + q, {"Authorization": f"Bearer {KEY}"} if KEY else {}),
             (base + q + "&model=flux" + (f"&key={KEY}" if KEY else ""), {})]
    for n in range(6):
        url, hdr = tries[n % 3]
        try:
            r = requests.get(url, headers=hdr, timeout=120)
            print("try", n + 1, "status", r.status_code, r.headers.get("content-type"), len(r.content))
            if r.ok and "image" in r.headers.get("content-type", "") and len(r.content) > 20000:
                open("pic.jpg", "wb").write(r.content)
                return Image.open("pic.jpg").convert("RGB")
            print("reply:", r.text[:300] if "image" not in r.headers.get("content-type", "") else "small image")
        except Exception as e:
            print("image error:", e)
        time.sleep(15)
    sys.exit("Could not make the picture. Stopping.")

pic = get_image()

# 3. build one 9:16 frame
W, H = 1080, 1920
bg = pic.resize((W, H)).filter(ImageFilter.GaussianBlur(40))
bg = Image.eval(bg, lambda v: int(v * 0.45))
pic = pic.resize((960, 1200))
bg.paste(pic, (60, 330))
d = ImageDraw.Draw(bg)
def font(sz):
    for p in ("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",):
        if os.path.exists(p):
            return ImageFont.truetype(p, sz)
    return ImageFont.load_default()
def center(text, y, sz, fill="white"):
    f = font(sz)
    w = d.textlength(text, font=f)
    d.text(((W - w) / 2, y), text, font=f, fill=fill)
center("FREE AI PROMPT", 110, 70, "#ff5c8a")
center(title, 210, 64)
center("Copy the full prompt FREE", 1590, 62)
center(SITE, 1690, 56, "#ffd166")
center("Link in bio", 1780, 48)
bg.save("frame.png")

# 4. frame -> 12 second video with a slow zoom
subprocess.run([
    "ffmpeg", "-y", "-loop", "1", "-i", "frame.png",
    "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo",
    "-vf", "zoompan=z='min(zoom+0.0007,1.12)':d=300:s=1080x1920:fps=25,format=yuv420p",
    "-t", "12", "-c:v", "libx264", "-c:a", "aac", "-shortest", "out.mp4"],
    check=True, capture_output=True)
print("Video made: out.mp4")

# 5. post to Instagram (only if the secrets are set)
if not (UID and TOKEN):
    print("No Instagram secrets yet. Video saved only.")
    sys.exit(0)

with open("out.mp4", "rb") as f:
    vurl = requests.post("https://catbox.moe/user/api.php",
                         data={"reqtype": "fileupload"}, files={"fileToUpload": f}, timeout=300).text.strip()
print("Video link:", vurl)
caption = (f"{title}\n\nCopy this prompt FREE: {SITE} (link in bio)\n\n"
           "#aiprompts #geminiprompts #chatgptprompts #aiimage #promptengineering #aiart #indianaiart")
G = f"https://graph.instagram.com/v21.0/{UID}"
c = requests.post(G + "/media", data={"media_type": "REELS", "video_url": vurl,
                                       "caption": caption, "access_token": TOKEN}).json()
print(c)
cid = c["id"]
for _ in range(40):
    s = requests.get(f"https://graph.instagram.com/v21.0/{cid}",
                     params={"fields": "status_code", "access_token": TOKEN}).json()
    print(s)
    if s.get("status_code") == "FINISHED":
        break
    if s.get("status_code") == "ERROR":
        sys.exit("Instagram could not process the video.")
    time.sleep(10)
print(requests.post(G + "/media_publish", data={"creation_id": cid, "access_token": TOKEN}).json())
