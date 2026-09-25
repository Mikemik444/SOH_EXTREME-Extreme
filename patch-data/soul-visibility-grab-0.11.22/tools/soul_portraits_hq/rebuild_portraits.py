"""Recompose SOH-EXTREME enemy portraits from the supplied ORIGINAL artwork.
Requires Pillow and NumPy only to regenerate assets, not to build/run the game.
No online files, font files or game ROM are needed.
"""
from pathlib import Path
import json, argparse, hashlib
from PIL import Image, ImageChops, ImageDraw, ImageEnhance, ImageFilter
import numpy as np

def generate(source: Path, mapping: Path, output: Path, preview: Path):
    entries=json.loads(mapping.read_text())
    sheet=Image.open(source/'portraits-contact.png').convert('RGB')
    base=Image.open(source/'shared-soul-base.rgba32.png').convert('RGBA')
    # Keep the familiar horned soul silhouette, but lower its brightness and
    # opacity: it frames the enemy instead of competing with a tiny face icon.
    backing=base.resize((128,128),Image.Resampling.LANCZOS)
    backing=ImageEnhance.Brightness(backing).enhance(0.48)
    backing.putalpha(backing.getchannel('A').point(lambda a: round(a*0.55)))
    results=[];images=[]
    for i,e in enumerate(entries):
        x=(i%8)*140;y=(i//8)*156
        im=sheet.crop((x+4,y+4,x+136,y+127)).convert('RGBA')
        a=np.array(im);delta=np.max(np.abs(a[:,:,:3].astype(np.int16)-np.array([25,31,42])),axis=2)
        a[:,:,3]=np.where(delta<=1,0,255).astype(np.uint8)
        im=Image.fromarray(a)
        if e['key']=='STALFOS':im=Image.open(source/'stalfos.png').convert('RGBA')
        bbox=im.getchannel('A').getbbox()
        if bbox is None:raise ValueError('Empty original portrait: '+e['key'])
        im=im.crop(bbox)
        if e['key']=='JABU_TENTACLE':im=im.rotate(25,Image.Resampling.BICUBIC,expand=True)
        # Very dark original portraits need stronger lifting. Do not synthesize
        # details: all body shapes and internal surfaces stay from the source.
        lift={'DARK_LINK':2.6,'KEESE':1.65,'WALLMASTER':1.35,'FLOORMASTER':1.35}.get(e['key'],1.18)
        im=ImageEnhance.Brightness(im).enhance(lift)
        im=ImageEnhance.Contrast(im).enhance(1.06)
        # Enemy reaches up to 116/128 pixels instead of 190/256 -> 24/32 pixels.
        k=min(116/im.width,116/im.height)
        im=im.resize((max(1,round(im.width*k)),max(1,round(im.height*k))),Image.Resampling.LANCZOS)
        im=im.filter(ImageFilter.UnsharpMask(radius=0.6,percent=65,threshold=3))
        pos=((128-im.width)//2,(128-im.height)//2)
        matte=Image.new('L',(128,128));matte.paste(im.getchannel('A'),pos)
        # Narrow dark separation outside the body, then a thin light silhouette.
        # Neither is painted over the enemy's face or flattened into its details.
        dark=Image.new('RGBA',(128,128),(5,10,17,0))
        dark.putalpha(matte.filter(ImageFilter.MaxFilter(7)).point(lambda a:round(a*0.94)))
        light=Image.new('RGBA',(128,128),(201,235,247,0))
        edge=ImageChops.subtract(matte.filter(ImageFilter.MaxFilter(3)),matte)
        light.putalpha(edge.point(lambda a:round(a*0.82)))
        hq=Image.alpha_composite(backing,dark);hq=Image.alpha_composite(hq,light);hq.alpha_composite(im,pos)
        # Strip invisible RGB: preserves smooth edges when the GPU filters alpha.
        hq_arr=np.array(hq);hq_arr[hq_arr[:,:,3]==0,:3]=0;hq=Image.fromarray(hq_arr)
        folder=output/'soh/assets/custom/textures/parameter_static';folder.mkdir(parents=True,exist_ok=True)
        hp=folder/f"gExtremeSoulHQ_{e['key']}.rgba32.png";hq.save(hp)
        hud=hq.resize((32,32),Image.Resampling.LANCZOS)
        lp=folder/f"gExtremeSoul_{e['key']}.rgba32.png";hud.save(lp)
        assert hq.size==(128,128) and hq.getchannel('A').getextrema()[0]==0
        images.append((e['key'],hq,hud))
        results.append({'item':e['item'],'hq':str(hp.relative_to(output)),'hud':str(lp.relative_to(output)),
                        'hq_size':[128,128],'hud_size':[32,32], 'portrait_bounds':[pos[0],pos[1],*im.size],
                        'hq_sha256':hashlib.sha256(hp.read_bytes()).hexdigest(),
                        'hud_sha256':hashlib.sha256(lp.read_bytes()).hexdigest()})
    assert len({r['hq_sha256'] for r in results})==47
    preview.mkdir(parents=True,exist_ok=True)
    contact=Image.new('RGB',(8*150,6*154),(25,31,42));d=ImageDraw.Draw(contact)
    for i,(key,hq,hud) in enumerate(images):
        x=i%8*150;y=i//8*154;contact.paste(hq,(x+11,y+3),hq);d.text((x+3,y+134),key,fill=(235,240,248))
    contact.save(preview/'enemy-portraits-128.png')
    (preview/'assets.json').write_text(json.dumps(results,indent=2)+'\n')
    return results

if __name__=='__main__':
    p=argparse.ArgumentParser();here=Path(__file__).resolve().parent
    p.add_argument('--source',type=Path,default=here/'portraits')
    p.add_argument('--mapping',type=Path,default=here/'enemy-soul-assets.json')
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--preview',type=Path,default=here/'preview')
    a=p.parse_args();print('Rebuilt',len(generate(a.source,a.mapping,a.output,a.preview)),'HQ and HUD portrait pairs')
