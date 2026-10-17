"""Small minted gold coins: cached artwork, ballistic motion and soft glints."""
from dataclasses import dataclass
import math,random,time
from PySide6.QtCore import QObject,QPointF,QRectF,Qt,QTimer
from PySide6.QtGui import (QColor,QImage,QLinearGradient,QPainter,QPainterPath,
                          QPen,QPixmap,QRadialGradient)

_ATLAS=None

def _coin_atlas():
    global _ATLAS
    if _ATLAS is not None:return _ATLAS
    frames=[]
    for index in range(48):
        angle=index*math.tau/48;face=max(.035,abs(math.cos(angle)))
        width=24*face;edge=4.2*math.sin(angle)
        im=QImage(72,72,QImage.Format.Format_ARGB32_Premultiplied);im.fill(Qt.GlobalColor.transparent)
        p=QPainter(im);p.setRenderHint(QPainter.RenderHint.Antialiasing);p.translate(36,36)
        # A real-looking side wall remains visible when the face turns edge-on.
        metal=QLinearGradient(0,-24,0,24)
        for stop,color in [(0,'#fff0a3'),(.14,'#d49c28'),(.3,'#fff5bc'),(.48,'#a66812'),(.64,'#f8ce61'),(1,'#9c5c10')]:metal.setColorAt(stop,QColor(color))
        p.setPen(QPen(QColor('#8c5814'),.6));p.setBrush(metal)
        p.drawRoundedRect(QRectF(min(0,edge)-width,-24,2*width+abs(edge),48),max(.5,width),max(.5,width))
        if abs(edge)>1.3:
            p.setPen(QPen(QColor(109,66,10,150),.7))
            for y in range(-20,23,4):
                rim=math.sqrt(max(0,1-(y/24)**2))
                p.drawLine(QPointF(-width*rim,y),QPointF(edge-width*rim,y+.35))
                p.drawLine(QPointF(width*rim,y),QPointF(edge+width*rim,y+.35))
        p.translate(edge,0);p.scale(face,1)
        bevel=QLinearGradient(-19,-24,18,24)
        for stop,color in [(0,'#fff7cd'),(.2,'#ffdf7c'),(.47,'#bd7c18'),(.64,'#ffe690'),(1,'#996013')]:bevel.setColorAt(stop,QColor(color))
        p.setPen(QPen(QColor('#b57b22'),.7));p.setBrush(bevel);p.drawEllipse(QRectF(-24,-24,48,48))
        field=QLinearGradient(-17,-23,20,24)
        for stop,color in [(0,'#fff3b0'),(.25,'#f7cc58'),(.46,'#e4a72a'),(.55,'#ffdf74'),(.83,'#d3931b'),(1,'#edbe49')]:field.setColorAt(stop,QColor(color))
        p.setPen(QPen(QColor('#a56a16'),.9));p.setBrush(field);p.drawEllipse(QRectF(-19.8,-19.8,39.6,39.6))
        p.setBrush(Qt.BrushStyle.NoBrush);p.setPen(QPen(QColor('#fff2b0'),.75));p.drawArc(QRectF(-22,-22,44,44),18*16,139*16)
        # Fine milled rim and a recessed lozenge keep this from reading as dots.
        for tooth in range(28):
            a=tooth*math.tau/28
            p.setPen(QPen(QColor('#a66e1c') if tooth%2 else QColor('#fff0a1'),.65))
            p.drawLine(QPointF(20.9*math.cos(a),20.9*math.sin(a)),QPointF(22.2*math.cos(a),22.2*math.sin(a)))
        stamp=QPainterPath();stamp.moveTo(0,-10);stamp.lineTo(7.5,0);stamp.lineTo(0,10);stamp.lineTo(-7.5,0);stamp.closeSubpath()
        p.save();p.translate(.7,1);p.setPen(QPen(QColor('#fff0a0'),1.2));p.drawPath(stamp);p.restore()
        p.setBrush(QColor(164,105,17,80));p.setPen(QPen(QColor('#b67b1c'),1.3));p.drawPath(stamp)
        p.setPen(QPen(QColor('#fff0ac'),.9));p.drawLine(QPointF(-11,-3),QPointF(-11,3));p.drawLine(QPointF(11,-3),QPointF(11,3))
        p.setPen(QPen(QColor(255,255,223,215),1.7));p.drawArc(QRectF(-23,-23,46,46),48*16,43*16)
        p.end();frames.append(QPixmap.fromImage(im))
    _ATLAS=frames;return frames

@dataclass(slots=True)
class Coin:
    born:float;x:float;y:float;vx:float;vy:float;gravity:float
    life:float;radius:float;phase:float;flip:float;roll:float;spin:float

@dataclass(slots=True)
class Glint:
    born:float;x:float;y:float;vx:float;vy:float;life:float;size:float;angle:float

class CoinBurst(QObject):
    def __init__(self,parent,clock=time.monotonic):
        super().__init__(parent);self.clock=clock;self.rng=random.Random()
        self.coins=[];self.glints=[];self.atlas=_coin_atlas()
        self.timer=QTimer(self);self.timer.setTimerType(Qt.TimerType.PreciseTimer);self.timer.setInterval(16)
        self.timer.timeout.connect(self.tick)

    def clear(self):
        self.timer.stop();self.coins.clear();self.glints.clear()

    def tick(self):
        now=self.clock()
        self.coins[:]=[c for c in self.coins if now-c.born<c.life]
        self.glints[:]=[g for g in self.glints if now-g.born<g.life]
        if not self.coins and not self.glints:self.timer.stop()
        self.parent().update()

    def burst(self,point,bounds,scale=1.):
        now=self.clock();self.tick();r=self.rng;scale=max(.7,min(1.5,scale))
        # Leave room for the entire rotating coin even at the widget's edge.
        margin=14*scale
        if bounds.width()<margin*2+1 or bounds.height()<margin*2+1:return
        ox=max(margin,min(bounds.width()-margin,point.x()))
        oy=max(margin,min(bounds.height()-margin,point.y()))
        count=7 if len(self.coins)<21 else 4
        for i in range(count):
            radius=r.uniform(6.8,9.6)*scale;gravity=420*scale
            vy=-min(r.uniform(135,205)*scale,math.sqrt(2*gravity*max(0,oy-margin))*.9)
            exit_time=(-vy+math.sqrt(vy*vy+2*gravity*(bounds.height()-margin-oy)))/gravity
            life=max(.12,min(r.uniform(.78,1.05),exit_time*.96))
            target=max(margin,min(bounds.width()-margin,ox+(i-(count-1)/2)*27*scale+r.uniform(-10,10)*scale))
            self.coins.append(Coin(now+r.uniform(0,.045),ox,oy,(target-ox)/life,vy,gravity,life,radius,r.uniform(0,math.tau),r.uniform(13,22),r.uniform(-30,30),r.uniform(-70,70)))
        self.coins[:]=self.coins[-42:]
        for i in range(5):
            angle=r.uniform(-math.pi,0);speed=r.uniform(28,70)*scale
            self.glints.append(Glint(now+r.uniform(.015,.15),ox,oy,math.cos(angle)*speed,math.sin(angle)*speed,r.uniform(.28,.55),r.uniform(2.1,3.5)*scale,r.uniform(-.3,.3)))
        self.glints[:]=self.glints[-30:];self.timer.start();self.parent().update()

    def paint(self,p):
        now=self.clock();p.save();p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        for c in self.coins:
            t=now-c.born
            if not 0<=t<c.life:continue
            progress=t/c.life;fade=max(0,min(1,(1-progress)/.3));fade=fade*fade*(3-2*fade)
            x=c.x+c.vx*t;y=c.y+c.vy*t+.5*c.gravity*t*t
            p.save();p.translate(x,y);p.rotate(c.roll+c.spin*t);p.setOpacity(fade*min(1,t/.025))
            radius=c.radius*(.82+.18*min(1,t/.07))
            phase=c.phase+c.flip*t
            atlas=self.atlas[int(phase/math.tau*len(self.atlas))%len(self.atlas)]
            # The atlas has transparent padding around a 48 px coin.
            extent=radius*1.5
            p.drawPixmap(QRectF(-extent,-extent,extent*2,extent*2),atlas,QRectF(atlas.rect()))
            p.restore()
        for g in self.glints:
            t=now-g.born
            if not 0<=t<g.life:continue
            power=math.sin(math.pi*t/g.life)**1.4;size=g.size*power
            p.save();p.translate(g.x+g.vx*t,g.y+g.vy*t);p.rotate(g.angle*180/math.pi)
            glow=QRadialGradient(0,0,size*3);glow.setColorAt(0,QColor(255,218,122,75));glow.setColorAt(1,QColor(255,200,75,0))
            p.setOpacity(power);p.setPen(Qt.PenStyle.NoPen);p.setBrush(glow);p.drawEllipse(QPointF(),size*3,size*3)
            star=QPainterPath();star.moveTo(0,-size*1.45)
            for x,y in [(size*.22,-size*.22),(size,0),(size*.22,size*.22),(0,size*1.45),(-size*.22,size*.22),(-size,0),(-size*.22,-size*.22)]:star.lineTo(x,y)
            star.closeSubpath();p.setBrush(QColor('#fff1be'));p.drawPath(star)
            p.setBrush(QColor('#fffbed'));p.drawEllipse(QPointF(),size*.17,size*.17);p.restore()
        p.restore()
