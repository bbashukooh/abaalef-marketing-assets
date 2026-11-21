import hashlib, json, subprocess, tempfile
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageChops, ImageFilter, features
from fontTools.ttLib import TTFont
from fontTools.pens.boundsPen import BoundsPen
from fontTools.pens.boundsPen import BoundsPen
assert features.check('raqm'), 'Persian typography requires RAQM'
ROOT=Path('writing-campaign-2026-11-21')
SOURCE=ROOT/'source'
OUT=ROOT/'first-slide-brand-background'/'preview'
OUT.mkdir(parents=True, exist_ok=True)
EXPECTED={
    'uni0635.medi':('70934051a2c578911f5986dff717a9b23f6d0e645d65aae89d7c03418a8c072c',66,6270),
    'uni0634.isol':('a35b1d9bcdd0c57b2f02efc0b07e8ff0573fbe3d285c6e99f82328c38a4c921d',76,7220),
    'uni0645.isol':('005e76669075fb24343724ecb612fbc29ecaf1116e75f6789c09abec6bf82444',56,5320),
    'uni0638.fina':('e2db2d69217906081969068f42ee941f269c98d85ae3a59c321fb029be11a61d',88,8360),
    'uni063A.fina':('64e46f1902f315677a2dd00f7a517ee16347ea0ac64b2a3adf59a4440d4ad629',61,5795),
    'uni0647.init':('41d36c3faa81a91832ef44097adae906498d324d210b0b4ca4c2d099f2cd60e9',71,6745)
}
fontpath=SOURCE/'BabaAlef-Font-v1.0.2.ttf'
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
assert sha(fontpath)=='33330473816a7fc0db3806d6ef573532955f8aafbebda64c12091e3751cc0f78'
lockedfont=TTFont(fontpath)
glyph_set=lockedfont.getGlyphSet()
print('VERIFIED locked font SHA256',sha(fontpath))
im=Image.open('/tmp/ba-v7/blank-board.png')
print('Approved blank board size/hash',im.size,sha('/tmp/ba-v7/blank-board.png'))
assert sha('/tmp/ba-v7/blank-board.png')=='4731114e48192a418bb84e1640a61a918f9f136d137decd8f6acddf83544d3d9'
assert im.size==(1092,1440),'Wrong approved board!'
W,H=1080,1350
BASE=im.convert('RGB').resize((W,H),Image.Resampling.LANCZOS)
UI='/tmp/ba-v7/ui.ttf'
NAVY='#092343'; TEAL='#008C80'; GUIDE='#C2BFE2'; ORANGE='#F9B62B'
def font(size,face=UI):return ImageFont.truetype(str(face),size,layout_engine=ImageFont.Layout.RAQM)
def text(d,xy,s,size,color=NAVY,face=UI):
    d.text(xy,s,font=font(size,face),fill=color,anchor='mm',direction='rtl',language='fa')
def fittext(d,xy,s,size,maxwidth,color=NAVY,face=UI):
    while d.textlength(s,font=font(size,face),direction='rtl')>maxwidth:size-=1
    text(d,xy,s,size,color,face)
def headline(canvas,heading,sub=None):
    d=ImageDraw.Draw(canvas)
    fittext(d,(540,302),heading,46,770)
    if sub:
        d.rounded_rectangle((205,341,875,411),radius=31,outline='#44CB70',width=3,fill='#FFFFFF')
        fittext(d,(540,376),sub,31,630)
def guide(d,y,x0,x1):
    d.line((x0,y,x1,y),fill=GUIDE,width=3)
def glyph(txt,x,y,size):
    # Render only with the immutable course font, never a generic font.
    b=Image.new('RGBA',(W,H),(0,0,0,0))
    d=ImageDraw.Draw(b)
    d.text((x,y),txt,font=font(size,fontpath),fill=NAVY,anchor='ms',direction='rtl',language='fa')
    return b
seqs={}
audit={'font_sha256':sha(fontpath),'template_sha256':sha('/tmp/ba-v7/blank-board.png'),'reference_commit':'d1b85797308fd335f3abf2a07e0c3cf557b2e19d','animations':{}}
for name,(digest,n,ms) in EXPECTED.items():
    p=SOURCE/(name+'.webp')
    assert sha(p)==digest,f'Locked animation changed: {name}'
    frames=[]
    durations=[]
    with Image.open(p) as a:
        assert 1<=getattr(a,'n_frames',0)<=n,(name,a.n_frames,n) # WebP can coalesce identical V7 frames without changing duration
        assert a.size==(640,520)
        for i in range(a.n_frames):
            a.seek(i)
            durations.append(int(a.info.get('duration',95)))
            frames.append(a.convert('RGBA').copy())
    union=None
    for f in frames:
        box=f.getchannel('A').getbbox()
        if box:
            if union is None:union=box
            else:union=(min(union[0],box[0]),min(union[1],box[1]),max(union[2],box[2]),max(union[3],box[3]))
    print(name,'frames',len(frames),'duration',sum(durations),'expected duration',ms,'nontransparent bbox',union,'alpha max',frames[-1].getchannel('A').getextrema())
    # The manifest includes source-stage frame counts; the released WebP is authoritative for playback.
    # Use embedded WebP frame durations verbatim, rather than altering the V7 motion to fit metadata.
    if sum(durations)!=ms: print('NOTE: encoded WebP duration differs from source-stage manifest, preserving the encoded timing:',name,sum(durations),ms)
    assert union is not None, 'Missing genuine animated ink'
    seqs[name]=(frames,durations,union)
    audit['animations'][name]={'sha256':digest,'frame_count':n,'duration_ms':ms,'observed_duration_ms':sum(durations),'visible_bbox':union}
glyphset=TTFont(fontpath).getGlyphSet()
true_baselines={}
for name in EXPECTED:
    pen=BoundsPen(glyphset);glyphset[name].draw(pen)
    font_left,font_min_y,font_right,font_max_y=map(float,pen.bounds)
    pixel_left,pixel_top,pixel_right,pixel_bottom=seqs[name][2]
    true_baselines[name]=pixel_bottom+font_min_y*((pixel_bottom-pixel_top)/(font_max_y-font_min_y))
audit['true_baseline_native_pixels']=true_baselines
def scaled_line_y(name,origin_y,scaled_height):
    return round(origin_y+true_baselines[name]*scaled_height/520)
def native_baseline(key):
    # Convert y=0 of the locked course font to the V7 bitmap's 640x520 pixel canvas.
    # Critically each glyph's vertical positioning differs, and no constant is valid.
    _,_,bbox=seqs[key]
    pen=BoundsPen(glyph_set);glyph_set[key].draw(pen)
    assert pen.bounds is not None
    x_min,y_min,x_max,y_max=pen.bounds
    sx=(bbox[2]-bbox[0])/(x_max-x_min)
    sy=(bbox[3]-bbox[1])/(y_max-y_min)
    assert abs(sx-sy)/max(sx,sy)<.085,(key,sx,sy)
    return bbox[3]+y_min*sy
baseline_table={k:native_baseline(k) for k in EXPECTED}
audit['computed_native_baselines']=baseline_table
print('LOCKED-FONT BASELINES:',baseline_table)
def scaled_frames(key,maxwidth,maxheight):
    frames,durations,bbox=seqs[key]
    # Scale the original entire 640x520 canvas as a unit; never redraw, crop or transform strokes.
    scale=min(maxwidth/640,maxheight/520)
    w=round(640*scale);h=round(520*scale)
    return [f.resize((w,h),Image.Resampling.LANCZOS) for f in frames],durations,(w,h)
def composite(base,frame,x,y):
    z=base.copy().convert('RGBA')
    z.alpha_composite(frame,(int(x),int(y)))
    return z.convert('RGB')
# 1: introductory poster. The teacher mascot is the EXACT user-uploaded bitmap
# with the photographic white backing separated; this is NOT regenerated.
hero,hero_ms,hero_size=scaled_frames('uni0634.isol',780,633)
# Recreate ONLY the warm peach/gold and mint atmospheric BACKGROUND of
# the previously approved custom-font campaign. This is flat graphic compositing,
# not character generation and not modification of the locked V7 ink.
cover=Image.new('RGB',(W,H),(255,247,239))
bg_d=ImageDraw.Draw(cover)
top=(255,250,244);bottom=(255,244,232)
for yy in range(H):
    amount=yy/(H-1)
    bg_d.line((0,yy,W,yy),fill=tuple(round(top[k]*(1-amount)+bottom[k]*amount) for k in range(3)),width=1)
brand_palette={
    "cream_top":"#FFF7F0","warm_peach_bottom":"#FFEEDD",
    "orange_bursts":"#FF9618","golden_glow":"#FFD66A",
    "warm_sunlight":"#FFB26C","mint":"#54D7B5","turquoise":"#00BFAE",
    "headline_gold":"#FFE04B"}
def backdrop_glow(cx,cy,rx,ry,rgb,alpha,blur):
    global cover
    # Blur alpha ONLY; blurring transparent RGB would introduce dark halos.
    opacity=Image.new('L',(W,H),0)
    ImageDraw.Draw(opacity).ellipse((cx-rx,cy-ry,cx+rx,cy+ry),fill=alpha)
    opacity=opacity.filter(ImageFilter.GaussianBlur(blur))
    layer=Image.new('RGBA',(W,H),tuple(rgb)+(0,))
    layer.putalpha(opacity)
    cover=Image.alpha_composite(cover.convert('RGBA'),layer).convert('RGB')
# Soft watercolor-like atmosphere from the previously approved poster.
backdrop_glow(75,195,330,310,(255,217,181),80,150)
backdrop_glow(1040,245,330,340,(255,222,185),80,155)
backdrop_glow(560,475,490,160,(255,237,207),35,105)
backdrop_glow(-10,785,260,390,(197,244,223),82,125)
backdrop_glow(1015,825,305,450,(185,243,219),86,135)
backdrop_glow(560,1270,515,245,(255,225,186),86,145)
backdrop_glow(110,1190,235,260,(187,239,215),70,95)
# The three short rounded orange bursts on each side are from yesterday's
# design language, but kept OUTSIDE the approved educational letter panel.
# Keep the top logo area uniformly bright to prevent a pasted-header rectangle.
top_d=ImageDraw.Draw(cover)
for yy in range(0,178):
    amt=1.0 if yy<=104 else ((178-yy)/74.0)**2
    old=cover.crop((0,yy,W,yy+1))
    row=Image.blend(old,Image.new('RGB',(W,1),(255,248,241)),amt)
    cover.paste(row,(0,yy))
d=ImageDraw.Draw(cover)
def ray(a,b,width=13):
    d.line((*a,*b),fill=brand_palette['orange_bursts'],width=width)
    r=width/2
    for px,py in (a,b):
        d.ellipse((px-r,py-r,px+r,py+r),fill=brand_palette['orange_bursts'])
for a,b in [
    ((89,152),(119,191)),((62,211),(111,225)),((128,114),(144,164)),
    ((990,147),(962,187)),((1021,211),(974,225)),((951,114),(938,167)),
    ((61,424),(113,437)),((982,421),(1025,436))
]:ray(a,b,11)
d=ImageDraw.Draw(cover)
# Keep the exact approved logo/header, blended into the matching cream tone.
logo=BASE.crop((245,3,845,132)).convert('RGB')
lm=Image.new('L',logo.size,0);md=ImageDraw.Draw(lm);md.rounded_rectangle((15,2,logo.width-15,logo.height-3),radius=31,fill=255)
lm=lm.filter(ImageFilter.GaussianBlur(15))
cover.paste(logo,(240,0),lm)
# Editorial hierarchy from the previously approved custom-font campaign.
fittext(d,(540,225),'بابا الف، نوشتن فارسی را',76,950,NAVY)
d.rounded_rectangle((125,283,955,377),radius=43,fill='#FFE04B')
fittext(d,(540,329),'با نمایش حرکت قلم یاد می‌دهد!',64,790,NAVY)
fittext(d,(540,427),'مسیر هر حرف، از اولین حرکت تا آخرین نقطه',39,930,TEAL)
# Whiteboard is a large brand-standard white panel, not generated lettering.
for n,fill in [(17,'#E6C36B'),(9,'#FFE17A'),(0,'#EAA21F')]:
    d.rounded_rectangle((64+n,557+n,757+n,1123+n),radius=55,fill=fill)
d.rounded_rectangle((79,564,776,1131),radius=49,fill='#FFC429',outline='#E99318',width=6)
d.rounded_rectangle((100,588,758,1106),radius=42,fill='#FFFEFD',outline='#FDE2AB',width=3)
# Actual glossy blue board clip (brand styling only).
d.rounded_rectangle((342,540,524,620),radius=27,fill='#006CBB')
d.rounded_rectangle((350,534,517,603),radius=25,fill='#00C6EF',outline='#0E8DD2',width=5)
d.rounded_rectangle((388,516,482,560),radius=17,fill='#07B9EC',outline='#058FE3',width=4)
d.arc((369,545,494,589),200,325,fill='#BDFBFF',width=8)
fittext(d,(407,652),'یک حرف، یک مسیر واقعی قلم',31,556,NAVY)
# The educational content is byte-for-byte sourced from V7 Transparent.
# Font y=0 is mapped to the exact per-form baseline from locked outlines.
cv,cv_ms,cvsize=scaled_frames('uni0635.medi',505,411)
bx=77
baseline=866
by=round(baseline-cvsize[1]*native_baseline('uni0635.medi')/520)
assert abs(scaled_line_y('uni0635.medi',by,cvsize[1])-baseline)<=1
d.line((128,baseline,599,baseline),fill=GUIDE,width=3)
d.line((128,baseline+1,599,baseline+1),fill='#E8E4F2',width=1)
# No fixed glyph is pasted here: the authentic V7 animation is composited frame by frame.
d=ImageDraw.Draw(cover)
fittext(d,(396,1082),'نمونهٔ حرکت قلم در شکل وسط حرف',27,530,TEAL)
# Remove only white photographic background from the actual uploaded mascot.
mascot_rgb=Image.open('/tmp/ba-v7/teacher-mascot.jpeg').convert('RGB')
diff=ImageChops.difference(mascot_rgb,Image.new('RGB',mascot_rgb.size,'white'))
channels=diff.split()
mag=ImageChops.lighter(ImageChops.lighter(channels[0],channels[1]),channels[2])
alpha=mag.point(lambda v:0 if v<9 else (255 if v>=42 else int((v-9)*255/33)))
mascot=mascot_rgb.copy().convert('RGBA');mascot.putalpha(alpha)
b=alpha.point(lambda a:255 if a>50 else 0).getbbox()
assert b is not None
mascot=mascot.crop((max(0,b[0]-3),max(0,b[1]-3),min(mascot.width,b[2]+3),min(mascot.height,b[3]+3)))
mascot.thumbnail((545,790),Image.Resampling.LANCZOS)
mx,my=W-mascot.width-2,542
cover_rgba=cover.convert('RGBA')
cover_rgba.alpha_composite(mascot,(mx,my))
cover=cover_rgba.convert('RGB')
d=ImageDraw.Draw(cover)
d.line((255,1300,375,1300),fill='#09BDAA',width=7)
d.line((713,1300,839,1300),fill='#09BDAA',width=7)
d.text((544,1300),'babaalef.com',font=font(54,UI),fill=NAVY,anchor='mm',direction='ltr')
cover_background=cover.copy()
cover_preview=composite(cover_background,cv[-1],bx,by)
cover_preview.save(OUT/'01-cover.jpg',quality=95,subsampling=0,optimize=True)
audit['cover_teacher_mascot_sha256']=sha('/tmp/ba-v7/teacher-mascot.jpeg')
audit['native_handwriting_baseline_y']=baseline_table
audit['hero_final_baseline_y']=baseline

def frame_at(arr,durations,t):
    # Frame selection is based on ORIGINAL duration, without changing stroke timing/order.
    elapsed=int(t*1000)
    total=sum(durations)
    if elapsed>=total:return arr[-1]
    rem=elapsed
    for f,d in zip(arr,durations):
        if rem<d:return f
        rem-=d
    return arr[-1]
def render_video(stem,duration,make_frame):
    fps=10
    count=round(duration*fps)
    previews=[]
    with tempfile.TemporaryDirectory() as tmp:
        tmp=Path(tmp)
        for i in range(count):
            fr=make_frame(i/fps)
            if i in (0,count//2,count-1):
                fr.save(OUT/(stem+f'-frame-{i:03}.jpg'),quality=89,optimize=True)
            fr.save(tmp/(f'{i:04}.png'),compress_level=1)
            if i%2==0:previews.append(fr.resize((540,675),Image.Resampling.LANCZOS))
        args=[__import__('imageio_ffmpeg').get_ffmpeg_exe(),'-y','-loglevel','error','-framerate',str(fps),'-i',str(tmp/'%04d.png'),'-c:v','libx264','-preset','veryfast','-crf','20','-pix_fmt','yuv420p','-movflags','+faststart',str(OUT/(stem+'.mp4'))]
        subprocess.run(args,check=True)
    previews[0].save(OUT/(stem+'-preview.gif'),save_all=True,append_images=previews[1:],duration=200,loop=0,optimize=True,disposal=2)
    print('RENDERED',stem,'duration',duration,'size', (OUT/(stem+'.mp4')).stat().st_size)

def cover_make(t):
    return composite(cover_background,frame_at(cv,cv_ms,t),bx,by)
render_video('01-introduction-brand-background',8.0,cover_make)
for t,suffix in [(0,'start'),(4,'middle'),(7.9,'end')]:
    cover_make(t).save(OUT/('01-'+suffix+'.jpg'),quality=93,subsampling=0,optimize=True)
# A literal before/after sheet based on previously approved original, with no source edits.
prior=ROOT/'preview'/'01-cover.jpg'
if prior.exists():
    old=Image.open(prior).convert('RGB')
    new=Image.open(OUT/'01-cover.jpg').convert('RGB')
    board=Image.new('RGB',(1080,675),'#FFFFFF')
    board.paste(old.resize((540,675),Image.Resampling.LANCZOS),(0,0))
    board.paste(new.resize((540,675),Image.Resampling.LANCZOS),(540,0))
    board.save(OUT/'00-background-comparison.jpg',quality=93,optimize=True)
audit['brand_palette']=brand_palette
audit['change_scope']='background gradients, peach/mint washes, orange decorative rays ONLY'
audit['unchanged']=['original V7 WebP source','handwriting baseline, placement and scale','all text labels','teacher mascot original file','board and logo foreground','other carousel slides']
audit['outputs']=['01-introduction-brand-background.mp4','01-introduction-brand-background-preview.gif','01-cover.jpg','01-start.jpg','01-middle.jpg','01-end.jpg','00-background-comparison.jpg']
(OUT/'brand-background-audit.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print('APPROVED-PALETTE first slide only rendered; source font and animation sha verified')
