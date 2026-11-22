#!/usr/bin/env python3
"""Render approved Baba Alef audio slides using locked still art and original audio.
No Descript source videos are used. Retains the exact approved glyph pixels.
"""
from __future__ import annotations
from pathlib import Path
from PIL import Image, ImageDraw, ImageFilter
from pydub import AudioSegment
import math
import subprocess

ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / "source"
FPS = 30
TEAL = (7, 185, 158)
W, H = 1092, 1440

LETTERS = [
    ("letter_u622.mp3", 821, 703),
    ("letter_u628.mp3", 566, 703),
    ("letter_u645.mp3", 311, 703),
    ("letter_u698.mp3", 821, 915),
    ("letter_u6af.mp3", 566, 915),
    ("letter_u686.mp3", 311, 915),
]
WORDS = [
    ("word_u645-627-645-627-646.mp3", 629, 630),
    ("word_u645-62f-631-633-647.mp3", 629, 749),
    ("word_u698-644-647.mp3", 629, 868),
    ("word_u622-628.mp3", 629, 987),
    ("word_u6a9-62a-627-628.mp3", 629, 1106),
]

def run(args):
    print("RUN", " ".join(map(str, args[:15])), "...", flush=True)
    subprocess.run(list(map(str,args)), check=True)

def glow(x: int, y: int, w: int, h: int, radius: int, dest: Path):
    # A transparent outline/glow; centre stays completely transparent.
    bbox = (round(x-w/2)-3, round(y-h/2)-3, round(x+w/2)+3, round(y+h/2)+3)
    mask = Image.new("L", (W,H), 0)
    draw = ImageDraw.Draw(mask)
    draw.rounded_rectangle(bbox, radius=radius, outline=255, width=12)
    blurred = mask.filter(ImageFilter.GaussianBlur(17))
    back = Image.new("RGBA", (W,H), TEAL+(0,))
    blurred = blurred.point(lambda a: round(a * 0.47))
    back.putalpha(blurred)
    stroke = Image.new("RGBA", (W,H), (0,0,0,0))
    sd = ImageDraw.Draw(stroke)
    sd.rounded_rectangle(bbox, radius=radius, outline=TEAL+(230,), width=6)
    back = Image.alpha_composite(back, stroke)
    back.save(dest, optimize=True)

def make_slide(base_jpg: str, specs, width, height, radius, filename: str):
    still = SOURCE / base_jpg
    with Image.open(still) as img:
        assert img.size == (W,H), ("Unexpected image dimensions",still,img.size)
        print("Approved static slide", still.name, img.size, flush=True)
    audio_assets = []
    moments = []
    onset = 0.65
    for filename_mp3, x, y in specs:
        sound = AudioSegment.from_mp3(SOURCE / filename_mp3)
        sound = sound.set_frame_rate(44100).set_channels(2)
        seconds = len(sound)/1000
        audio_assets.append((onset, sound))
        moments.append((max(0,onset-.15), onset + seconds+.15,x,y))
        onset += seconds+1.20
    duration = audio_assets[-1][0] + len(audio_assets[-1][1])/1000 + .80
    timeline = AudioSegment.silent(duration=math.ceil(duration*1000),frame_rate=44100).set_channels(2)
    for start,snd in audio_assets:
        timeline=timeline.overlay(snd,position=round(start*1000))
    wav = ROOT / f"_temp-{filename}.wav"
    timeline.export(wav,format="wav")
    overlays=[]
    for i, (_, _, x, y) in enumerate(moments):
        p=ROOT/f"_temp-{filename}-{i:02}.png"
        glow(x,y,width,height,radius,p)
        overlays.append(p)
    cmd=["ffmpeg","-hide_banner","-loglevel","error","-y","-threads","2",
         "-loop","1","-framerate",str(FPS),"-i",str(still)]
    for overlay in overlays:
        cmd+=["-loop","1","-framerate",str(FPS),"-i",str(overlay)]
    cmd+=["-i",str(wav)]
    chain=[]
    latest="[0:v]"
    for idx,(start,end,x,y) in enumerate(moments):
        label=f"[hl{idx}]"
        chain.append(f"{latest}[{idx+1}:v]overlay=0:0:format=auto:enable='between(t,{start:.3f},{end:.3f})'{label}")
        latest=label
    chain.append(f"{latest}format=yuv420p[v]")
    cmd+=["-filter_complex",";".join(chain),"-map","[v]","-map",f"{len(overlays)+1}:a:0",
          "-t",f"{duration:.3f}","-r",str(FPS),"-c:v","libx264","-preset","veryfast",
          "-crf","21","-pix_fmt","yuv420p","-c:a","aac","-b:a","160k",
          "-movflags","+faststart",str(ROOT/filename)]
    run(cmd)
    for p in overlays+[wav]:
        p.unlink(missing_ok=True)
    print("COMPLETE",filename,"duration",duration,flush=True)

def concat_final():
    # User-approved order: Cover -> real practice video -> letters -> words.
    inputs=[
      ROOT/"01-cover.jpg", ROOT/"04-practice.mp4",
      ROOT/"02-letters-clean.mp4", ROOT/"03-words-clean.mp4",
    ]
    for p in inputs:
        assert p.exists(), p
    cmd=["ffmpeg","-hide_banner","-loglevel","error","-y","-threads","2",
         "-loop","1","-framerate","30","-t","3","-i",str(inputs[0])]
    for p in inputs[1:]: cmd+=["-i",str(p)]
    cmd+=["-f","lavfi","-t","3","-i","anullsrc=r=48000:cl=stereo"]
    filters=[]
    for i in range(4):
        filters.append(
           f"[{i}:v]scale=1080:1920:force_original_aspect_ratio=decrease:flags=lanczos,"
           "pad=1080:1920:(ow-iw)/2:(oh-ih)/2:color=0xFFF7ED,"
           f"setsar=1,fps=30,format=yuv420p,setpts=PTS-STARTPTS[v{i}]")
    filters.append("[4:a]aresample=48000,asetpts=PTS-STARTPTS[a0]")
    for i in range(1,4):
        filters.append(f"[{i}:a]aresample=48000,asetpts=PTS-STARTPTS[a{i}]")
    concat="".join(f"[v{i}][a{i}]" for i in range(4))
    filters.append(concat+"concat=n=4:v=1:a=1[v][a]")
    cmd+=["-filter_complex",";".join(filters),"-map","[v]","-map","[a]",
          "-c:v","libx264","-preset","veryfast","-crf","23","-pix_fmt","yuv420p",
          "-c:a","aac","-b:a","160k","-ar","48000","-ac","2","-movflags","+faststart",
          str(ROOT/"05-all-slides-clean-reordered.mp4")]
    run(cmd)
    print("COMPLETE 05-all-slides-clean-reordered.mp4",flush=True)

if __name__=="__main__":
    make_slide("02-letters-still.jpg",LETTERS,216,199,29,"02-letters-clean.mp4")
    make_slide("03-words-still.jpg",WORDS,596,110,23,"03-words-clean.mp4")
    concat_final()
