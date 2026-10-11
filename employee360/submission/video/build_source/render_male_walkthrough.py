from pathlib import Path
import json, wave, subprocess, shutil, textwrap
from PIL import Image, ImageDraw
root=Path.cwd(); out=root/'walkthrough_male'
ffmpeg=r'C:\ffmpeg\bin\ffmpeg.exe'; ffprobe=r'C:\ffmpeg\bin\ffprobe.exe'
segments=json.loads((out/'narration.json').read_text())
def run(args):
    p=subprocess.run([ffmpeg,'-hide_banner','-loglevel','error','-y',*args],cwd=out,capture_output=True,text=True)
    if p.returncode: raise RuntimeError(p.stderr)
def timestamp(t):
    ms=round(t*1000); return f'{ms//3600000:02d}:{ms//60000%60:02d}:{ms//1000%60:02d},{ms%1000:03d}'
raw_duration=0
for segment in segments:
    with wave.open(str(out/(segment['key']+'.wav'))) as w: raw_duration+=w.getnframes()/w.getframerate()
speed=raw_duration/540.0
assert 0.5<=speed<=2.0,speed
chapters=[]; allcaptions=[]; elapsed=0
for slide in range(1,9):
    items=[s for s in segments if s['slide']==slide]; parts=[]; captions=[]; offset=0
    for item in items:
        with wave.open(str(out/(item['key']+'.wav'))) as w: duration=w.getnframes()/w.getframerate()/speed
        parts.append("file '"+item['key']+".wav'")
        words=item['text'].split(); chunks=[words[n:n+10] for n in range(0,len(words),10)]
        count=0
        for chunk in chunks:
            start=offset+duration*count/len(words); count+=len(chunk); end=offset+duration*count/len(words)
            captions.append((start,end,' '.join(chunk)))
            allcaptions.append((elapsed+start,elapsed+end,' '.join(chunk)))
        offset+=duration
    (out/f'audio-{slide:02d}.txt').write_text('\n'.join(parts))
    run(['-f','concat','-safe','0','-i',f'audio-{slide:02d}.txt','-af',f'atempo={speed:.8f}',f'audio-{slide:02d}.wav'])
    srt='\n\n'.join(f'{n}\n{timestamp(start)} --> {timestamp(end)}\n'+textwrap.fill(text,width=95) for n,(start,end,text) in enumerate(captions,1))
    (out/f'captions-{slide:02d}.srt').write_text(srt+'\n',encoding='utf-8')
    shutil.copy2(root/'.ppt_build'/f'slide-{slide:02d}.png',out/f'slide-{slide:02d}.png')
    vf=f"scale=1138:640,pad=1280:720:71:0:color=0x102A40,subtitles=captions-{slide:02d}.srt:force_style='FontName=Arial,FontSize=14,PrimaryColour=&H00FFFFFF,OutlineColour=&H00102A40,Outline=1,Shadow=0,MarginV=10,Alignment=2'"
    run(['-loop','1','-framerate','10','-i',f'slide-{slide:02d}.png','-i',f'audio-{slide:02d}.wav','-vf',vf,'-t',str(offset),'-c:v','libx264','-preset','veryfast','-tune','stillimage','-crf','23','-pix_fmt','yuv420p','-c:a','aac','-b:a','96k','-ar','44100','-movflags','+faststart',f'part-{slide:02d}.mp4'])
    chapters.append({'slide':slide,'title':items[0]['title'],'start':elapsed,'duration':offset}); elapsed+=offset
    print(f'Slide {slide} encoded: {offset:.1f}s',flush=True)
(out/'video-parts.txt').write_text('\n'.join(f"file 'part-{i:02d}.mp4'" for i in range(1,9)))
run(['-f','concat','-safe','0','-i','video-parts.txt','-c','copy','-movflags','+faststart','Employee360_DQ_Full_Walkthrough.mp4'])
(out/'Employee360_DQ_Full_Walkthrough.srt').write_text('\n\n'.join(f'{n}\n{timestamp(s)} --> {timestamp(e)}\n{t}' for n,(s,e,t) in enumerate(allcaptions,1))+'\n',encoding='utf-8')
probe=json.loads(subprocess.check_output([ffprobe,'-v','error','-show_format','-show_streams','-of','json',str(out/'Employee360_DQ_Full_Walkthrough.mp4')],text=True))
duration=float(probe['format']['duration']); assert 300<=duration<=600,duration
assert any(s['codec_type']=='audio' for s in probe['streams'])
assert any(s['codec_type']=='video' and s['width']==1280 and s['height']==720 for s in probe['streams'])
run(['-i','Employee360_DQ_Full_Walkthrough.mp4','-f','null','-'])
(out/'VIDEO_VALIDATION.json').write_text(json.dumps({'duration_seconds':duration,'width':1280,'height':720,'audio':True,'captions':'burned in; estimated word timing within measured paragraphs','narrator':'Microsoft George; male synthetic narrator, not a voice clone','decode_check':'passed','chapters':chapters},indent=2))
# Sample one actual video frame per slide, so review covers the encoded result.
canvas=Image.new('RGB',(960,1160),'#E5EAF0'); draw=ImageDraw.Draw(canvas)
for index,ch in enumerate(chapters):
    run(['-ss',str(ch['start']+ch['duration']/2),'-i','Employee360_DQ_Full_Walkthrough.mp4','-frames:v','1',f'review-{index+1:02d}.jpg'])
    im=Image.open(out/f'review-{index+1:02d}.jpg'); im.thumbnail((480,270))
    x=(index%2)*480; y=(index//2)*290
    canvas.paste(im,(x,y+20)); draw.text((x+8,y+3),f'Slide {index+1}',fill='black')
canvas.save(out/'video_contact_sheet.jpg',quality=68)
print(json.dumps({'duration_seconds':duration,'video':str(out/'Employee360_DQ_Full_Walkthrough.mp4')},indent=2))

