"""Bounded exact-process window frames with a small contact sheet."""
import argparse
import json
import time
import uuid
from pathlib import Path
from PIL import Image,ImageDraw
import capture_window

OUTPUT=capture_window.OUTPUT
def main():
    p=argparse.ArgumentParser()
    p.add_argument('--capture',action='store_true')
    p.add_argument('--pid',type=int)
    p.add_argument('--birth')
    args=p.parse_args()
    if not args.capture:
        print(json.dumps({'status':'PLAN','max_frames':8,'interval_seconds':2.0,
                          'desktop_pixels_captured':False}));return 0
    if not(args.pid and args.birth and args.birth.isdecimal()):raise ValueError('EXACT_IDENTITY_REQUIRED')
    token=uuid.uuid4().hex;rows=[]
    for index in range(8):
        start=time.monotonic()
        try:
            result=capture_window.capture(args.pid,args.birth)
            rows.append({'index':index,'elapsed':round(index*2.0,2),
                         'status':'CAPTURED','path':result['path'],
                         'printwindow_returned':result['printwindow_returned'],
                         'grayscale_extrema':result['grayscale_extrema']})
        except Exception as error:
            rows.append({'index':index,'elapsed':round(index*2.0,2),
                         'status':'UNKNOWN','reason':str(error)[:80]})
        pause=2.0-(time.monotonic()-start)
        if index<7 and pause>0:time.sleep(pause)
    captured=[row for row in rows if row['status']=='CAPTURED']
    OUTPUT.mkdir(exist_ok=True)
    sheet_path=None
    if captured:
        sheet=Image.new('RGB',(640,180*((len(captured)+1)//2)),(32,32,32))
        draw=ImageDraw.Draw(sheet)
        for index,row in enumerate(captured):
            image=Image.open(row['path']).convert('RGB')
            image.thumbnail((312,152))
            x=(index%2)*320;y=(index//2)*180
            sheet.paste(image,(x+(320-image.width)//2,y+24))
            draw.text((x+8,y+5),f"frame {row['index']}",fill=(255,255,255))
        sheet_path=OUTPUT/('contact-'+token+'.png')
        sheet.save(sheet_path)
    report={'schema':'lc-owned-window-sequence-v1','pid':args.pid,'birth':args.birth,
            'frames':rows,'contact_sheet':str(sheet_path) if sheet_path else None,
            'visible_character_screen_verified':False}
    path=OUTPUT/('contact-'+token+'.json')
    with path.open('x',encoding='utf-8')as stream:
        json.dump(report,stream,indent=2);stream.write('\n')
    print(json.dumps({'status':'RECORDED','report':str(path),
                      'contact_sheet':report['contact_sheet'],'captured':len(captured)}))
    return 0
if __name__=='__main__':raise SystemExit(main())
