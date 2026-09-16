"""Render the app's simple geometric mark for the Windows shortcut."""
from pathlib import Path
from PIL import Image, ImageDraw

image=Image.new('RGBA',(256,256),(234,239,230,255))
draw=ImageDraw.Draw(image)
draw.rounded_rectangle((0,0,255,255),radius=52,fill='#e9eee8')
for points in [((66,190),(66,66),(194,66)),((66,128),(163,128)),((128,190),(194,190))]:
    draw.line(points,fill='#446647',width=17,joint='curve')
image.save(Path(__file__).parent/'Elsewhere.ico',sizes=[(16,16),(24,24),(32,32),(48,48),(64,64),(128,128),(256,256)])
