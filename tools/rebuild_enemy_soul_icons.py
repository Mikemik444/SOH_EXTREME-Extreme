"""Deterministic composition of the supplied soul base and supplied enemy portraits.
No image synthesis, online assets, fonts, or game-ROM bytes are bundled.
"""
from pathlib import Path
from PIL import Image, ImageChops, ImageEnhance, ImageFilter, ImageDraw
import numpy as np, json, hashlib, shutil
W=Path(__file__).resolve().parents[1]; N=W
refs=W/'source/portraits'
base=Image.open(refs/'shared-soul-base.rgba32.png').convert('RGBA').resize((256,256),Image.Resampling.LANCZOS)
sheet=Image.open(refs/'portraits-contact.png').convert('RGB')
entries=json.loads((W/'tools/enemy-soul-assets.json').read_text())
# The existing horned soul remains the shared backing. A slightly darkened face
# keeps the overlaid model recognizable without needing a different base per enemy.
face=Image.new('RGBA',(256,256));ImageDraw.Draw(face).ellipse((38,58,221,244),fill=(12,23,31,160))
face=face.filter(ImageFilter.GaussianBlur(7))
alpha=ImageChops.multiply(face.getchannel('A'),base.getchannel('A'));face.putalpha(alpha)
common=Image.alpha_composite(base,face)
previews=[];results=[]
for i,e in enumerate(entries):
 x=(i%8)*140;y=(i//8)*156
 crop=sheet.crop((x+4,y+4,x+136,y+127)).convert('RGBA')
 a=np.array(crop)
 bg=np.array([25,31,42])
 d=np.max(np.abs(a[:,:,:3].astype('int16')-bg),axis=2)
 # Contact sheet background is constant. Preserve dark surfaces/holes inside
 # each model; only remove that exact background and a 1-value rounding band.
 a[:,:,3]=np.where(d<=1,0,255).astype('uint8')
 crop=Image.fromarray(a)
 box=crop.getchannel('A').getbbox();assert box,e
 crop=crop.crop(box)
 if e['key']=='STALFOS':
  crop=Image.open(refs/'stalfos.png').convert('RGBA');crop=crop.crop(crop.getchannel('A').getbbox())
 if e['key']=='JABU_TENTACLE':
  crop=crop.rotate(25,Image.Resampling.BICUBIC,expand=True)
 # Keep the entire tentacle, angled for readability; lift dark Link's contrast.
 crop=ImageEnhance.Brightness(crop).enhance(1.9 if e['key']=='DARK_LINK' else 1.16)
 crop.thumbnail((190,190),Image.Resampling.LANCZOS)
 if max(crop.size)<190:
  scale=min(190/crop.width,190/crop.height)
  crop=crop.resize((round(crop.width*scale),round(crop.height*scale)),Image.Resampling.LANCZOS)
 pos=((256-crop.width)//2, max(35,143-crop.height//2))
 # A shared thin light edge helps black enemies remain readable at 32 pixels.
 matte=Image.new('L',(256,256));matte.paste(crop.getchannel('A'),pos)
 edge=matte.filter(ImageFilter.MaxFilter(5)).filter(ImageFilter.GaussianBlur(1.1))
 glow=Image.new('RGBA',(256,256),(161,209,223,0));glow.putalpha(edge.point(lambda p:round(p*.65)))
 icon=Image.alpha_composite(common,glow)
 icon.alpha_composite(crop,pos)
 icon=icon.resize((32,32),Image.Resampling.LANCZOS)
 # Canonical 32-bit alpha resource, same dimensions used by the message renderer.
 dst=N/e['texture'];dst.parent.mkdir(parents=True,exist_ok=True);icon.save(dst)
 previews.append(icon)
 results.append({'item':e['item'],'resource':e['resource'],'size':[32,32],'mode':icon.mode,'sha256':hashlib.sha256(dst.read_bytes()).hexdigest()})
contact=Image.new('RGB',(8*176,6*174),(25,31,42));draw=ImageDraw.Draw(contact)
for i,(e,im) in enumerate(zip(entries,previews)):
 x=i%8*176;y=i//8*174
 scaled=im.resize((128,128),Image.Resampling.NEAREST)
 contact.paste(scaled,(x+24,y+4),scaled)
 # A Pillow built-in bitmap font is drawn into the preview, no font file shipped.
 draw.text((x+4,y+140),e['key'],fill=(235,240,248))
out=W/'validation/results';out.mkdir(parents=True,exist_ok=True)
contact.save(out/'enemy-souls-preview.png')
(out/'assets.json').write_text(json.dumps(results,indent=2)+'\n')
assert len({r['sha256'] for r in results})==len(results)
print('Created',len(results),'unique RGBA32 icons')
