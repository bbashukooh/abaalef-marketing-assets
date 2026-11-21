#!/usr/bin/env python3
"""Third slide only: immutable V7 layers, identical true BabaAlef font scale."""
import hashlib, json, math, subprocess, tempfile
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, features
from fontTools.ttLib import TTFont
from fontTools.pens.boundsPen import BoundsPen
import imageio_ffmpeg

assert features.check("raqm"), "Persian shaping needs RAQM"
ROOT = Path("writing-campaign-2026-11-21")
SOURCES = ROOT / "source"
OUT = ROOT / "third-slide-fix" / "output"
OUT.mkdir(parents=True, exist_ok=True)
TEMPLATE = Path("/tmp/baba-approved-empty-board.png")
UI = Path("/tmp/vazirmatn-extrabold.ttf")
FONT = SOURCES / "BabaAlef-Font-v1.0.2.ttf"
W, H = 1080, 1350
TRUE_FONT_UNIT_SCALE = 0.42   # one physical px/font-unit value for ALL FOUR source glyphs
SOURCE_SIZES = (640, 520)
TARGET_BASELINES = {"top":580, "bottom":1030}
FONT_SHA = "33330473816a7fc0db3806d6ef573532955f8aafbebda64c12091e3751cc0f78"
BOARD_SHA = "4731114e48192a418bb84e1640a61a918f9f136d137decd8f6acddf83544d3d9"
GLYPHS = [
    # same four exact V7 assets as approved/reviewed third slide; never replace with generated lettering
    {"id":"uni063A.fina", "row":"top", "col":"left", "center":405,
     "sha":"64e46f1902f315677a2dd00f7a517ee16347ea0ac64b2a3adf59a4440d4ad629"},
    {"id":"uni0645.isol", "row":"top", "col":"right", "center":755,
     "sha":"005e76669075fb24343724ecb612fbc29ecaf1116e75f6789c09abec6bf82444"},
    {"id":"uni0647.init", "row":"bottom", "col":"left", "center":420,
     "sha":"41d36c3faa81a91832ef44097adae906498d324d210b0b4ca4c2d099f2cd60e9"},
    {"id":"uni0638.fina", "row":"bottom", "col":"right", "center":755,
     "sha":"e2db2d69217906081969068f42ee941f269c98d85ae3a59c321fb029be11a61d"},
]
def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()
assert digest(FONT)==FONT_SHA, "Locked BabaAlef font changed"
assert digest(TEMPLATE)==BOARD_SHA, "Wrong or modified empty board"
base=Image.open(TEMPLATE).convert("RGB")
assert base.size==(1092,1440), base.size
base=base.resize((W,H),Image.Resampling.LANCZOS)
tt=TTFont(FONT)
glyph_set=tt.getGlyphSet()
font_audit=[]
def ui_font(size):
    return ImageFont.truetype(str(UI),size,layout_engine=ImageFont.Layout.RAQM)
def rtl_text(draw,y,s,size,max_width,color="#092343"):
    f=ui_font(size)
    while draw.textlength(s,font=f,direction="rtl",language="fa")>max_width:
        size-=1
        f=ui_font(size)
    draw.text((W//2,y),s,font=f,anchor="mm",fill=color,direction="rtl",language="fa")
d=ImageDraw.Draw(base)
rtl_text(d,296,"چهار شکل، چهار حرکت قلم",44,800)
d.rounded_rectangle((205,340,875,410),radius=30,fill="#FFFFFF",outline="#44CB70",width=3)
rtl_text(d,376,"هر چهار حرف با یک اندازهٔ واقعی فونت",31,620)
d.line((540,438,540,1090),fill="#DDDDE5",width=2)
d.line((182,794,903,794),fill="#DDDDE5",width=2)
for target in TARGET_BASELINES.values():
    for x0,x1 in [(238,518),(575,905)]:
        d.line((x0,target,x1,target),fill="#C0BBDC",width=3)
# Read original immutable V7 compositing frames, unchanged strokes/brush/timing.
sequences=[]
for g in GLYPHS:
    key=g["id"]
    path=SOURCES/(key+".webp")
    assert path.exists(),f"Original locked V7 is missing: {path}"
    assert digest(path)==g["sha"],f"V7 hash does not match manifest for {key}"
    pen=BoundsPen(glyph_set)
    glyph_set[key].draw(pen)
    xmin,ymin,xmax,ymax=map(float,pen.bounds)
    assert ymin<ymax and xmin<xmax
    with Image.open(path) as source:
        assert source.size==SOURCE_SIZES, (key,source.size)
        frames=[]
        durations=[]
        for i in range(source.n_frames):
            source.seek(i)
            durations.append(int(source.info.get("duration",95)))
            frames.append(source.convert("RGBA").copy())
    # use the full end-frame alpha boundary to infer the per-file font scale
    bx0,by0,bx1,by1=frames[-1].getchannel("A").getbbox()
    native_scale_x=(bx1-bx0)/(xmax-xmin)
    native_scale_y=(by1-by0)/(ymax-ymin)
    assert abs(native_scale_x/native_scale_y-1)<.025, (key,native_scale_x,native_scale_y)
    native_scale=(native_scale_x+native_scale_y)/2
    # IMPORTANT: glyphs have been individually fit into original 640x520 WebP canvases.
    # Equal image dimensions are NOT equal font size. Undo that native fitting mathematically.
    correction=TRUE_FONT_UNIT_SCALE/native_scale
    sw=round(SOURCE_SIZES[0]*correction)
    sh=round(SOURCE_SIZES[1]*correction)
    effective_x=native_scale_x*sw/SOURCE_SIZES[0]
    effective_y=native_scale_y*sh/SOURCE_SIZES[1]
    assert abs(effective_x-TRUE_FONT_UNIT_SCALE)/TRUE_FONT_UNIT_SCALE<.018,(key,effective_x)
    assert abs(effective_y-TRUE_FONT_UNIT_SCALE)/TRUE_FONT_UNIT_SCALE<.018,(key,effective_y)
    native_baseline=by1 + ymin*native_scale_y  # font y=0, NOT a guessed source-canvas line
    target=TARGET_BASELINES[g["row"]]
    px=int(round(g["center"]-(bx0+bx1)*sw/(2*SOURCE_SIZES[0])))
    py=int(round(target-native_baseline*sh/SOURCE_SIZES[1]))
    # Final visual bounding box, for no-overlap and in-panel assertion.
    visual=(px+bx0*sw/640,py+by0*sh/520,
            px+bx1*sw/640,py+by1*sh/520)
    assert 205<visual[0] and visual[2]<920, (key,visual)
    assert 417<visual[1] and visual[3]<1115, (key,visual)
    assert (visual[1]>794 if g["row"]=="bottom" else visual[3]<794), (key,visual)
    assert (visual[2]<540 if g["col"]=="left" else visual[0]>540), (key,visual)
    scaled=[fr.resize((sw,sh),Image.Resampling.LANCZOS) for fr in frames]
    sequences.append((g,scaled,durations,(px,py)))
    font_audit.append({
      "id":key,"font_outline_units":[xmin,ymin,xmax,ymax],
      "native_scale_px_per_font_unit":{"x":native_scale_x,"y":native_scale_y},
      "target_px_per_font_unit":TRUE_FONT_UNIT_SCALE,
      "actual_px_per_font_unit":{"x":effective_x,"y":effective_y},
      "original_sha256":g["sha"],"frames":len(frames),
      "source_webp_duration_ms":sum(durations),
      "origin":[px,py],"pixel_size":[sw,sh],
      "font_baseline_y_in_original_canvas":native_baseline,
      "aligned_guideline_y":target,"visual_bounds":visual
    })
# For a real baseline, the line is drawn first, V7 shapes then overlay it.
def frame_at(frames,durations,t_ms):
    if t_ms>=sum(durations): return frames[-1]
    elapsed=0
    for frame,dt in zip(frames,durations):
        elapsed+=dt
        if t_ms<elapsed:return frame
    return frames[-1]
def produce(t_ms):
    image=base.copy().convert("RGBA")
    for g,frames,durations,(x,y) in sequences:
        image.alpha_composite(frame_at(frames,durations,t_ms),(x,y))
    return image.convert("RGB")
duration_s=8
fps=20
count=duration_s*fps
with tempfile.TemporaryDirectory() as temp:
    temp=Path(temp)
    for n in range(count):
        frame=produce(n*1000/fps)
        frame.save(temp/f"{n:04d}.png",compress_level=1)
        if n in (0,79,count-1):
            frame.save(OUT/f"03-frame-{n:03d}.jpg",quality=95,subsampling=0,optimize=True)
    ffmpeg=imageio_ffmpeg.get_ffmpeg_exe()
    subprocess.run([ffmpeg,"-y","-loglevel","error","-framerate",str(fps),"-i",
      str(temp/"%04d.png"),"-c:v","libx264","-preset","veryfast","-crf","20",
      "-pix_fmt","yuv420p","-movflags","+faststart",str(OUT/"03-four-forms-equal-font-size.mp4")],check=True)
# Provenance and independent checks, including common physical scale.
assert len(font_audit)==4
assert all(abs(v["actual_px_per_font_unit"]["x"]-TRUE_FONT_UNIT_SCALE)<.009 for v in font_audit)
assert all(abs(v["actual_px_per_font_unit"]["y"]-TRUE_FONT_UNIT_SCALE)<.009 for v in font_audit)
report={
  "status":"independent review draft; not published or scheduled",
  "font":"BabaAlef-Font-v1.0.2.ttf","font_sha256":FONT_SHA,
  "original_reference":"BabaAlef-V7-Transparent", "board_sha256":BOARD_SHA,
  "definition_of_equal_size":"All 4 glyphs use the same 0.42 final pixels per original font design unit, NOT the same WebP canvas scale or bounding-box height",
  "common_target_pixels_per_font_unit":TRUE_FONT_UNIT_SCALE,
  "no_strokes_redrawn":True,"original_webp_frames_and_timing_used":True,
  "output_video":"03-four-forms-equal-font-size.mp4","video_fps":fps,"glyphs":font_audit
}
(OUT/"03-audit.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print("VERIFIED: ALL FOUR V7 SHAs MATCH. COMMON FONT SCALE",TRUE_FONT_UNIT_SCALE)
print(json.dumps(font_audit,ensure_ascii=False,indent=2))
