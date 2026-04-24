import React, { useEffect, useRef, useState } from 'react';

interface Particle {
  x: number;
  y: number;
  tgX: number; // Target X (database shape)
  tgY: number; // Target Y (database shape)
  scX: number; // Scatter anchor X
  scY: number; // Scatter anchor Y
  vx: number;
  vy: number;
  size: number;
  color: string;
  angle: number; 
  speed: number;
  isRogue: boolean; // TRUE: Particle never assembles, remains drifting
}

interface ParticleDatabaseProps {
  width?: number;
  height?: number;
  particleCount?: number;
  assembled?: boolean;
}

export const ParticleDatabase: React.FC<ParticleDatabaseProps> = ({ 
  particleCount = 1500, // More prominent density
  assembled = false
}) => {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [internalHover, setInternalHover] = useState(false);
  const particlesRef = useRef<Particle[]>([]);
  const animationRef = useRef<number>();
  const fadeFactorRef = useRef(0); // 0 (idle) to 1 (hovered/assembled)
  
  // Make the canvas natively track the full window viewport
  const [dims, setDims] = useState({ w: window.innerWidth, h: window.innerHeight });
  useEffect(() => {
    const onResize = () => setDims({ w: window.innerWidth, h: window.innerHeight });
    window.addEventListener('resize', onResize);
    return () => window.removeEventListener('resize', onResize);
  }, []);

  const width = dims.w;
  const height = dims.h;
  const isAssembled = assembled || internalHover;

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    // Safety check for dimensions
    if (width <= 0 || height <= 0) return;

    // 1. Generate Target Points using an offscreen canvas to sample a pure SVG Database Icon
    const offCanvas = document.createElement('canvas');
    offCanvas.width = width;
    offCanvas.height = height;
    const offCtx = offCanvas.getContext('2d');
    
    // Lock the database icon behind the new right-aligned widget card layout
    const baseIconSize = 520; 
    const containerWidth = Math.min(width, 1200);
    const containerLeft = Math.max((width - 1200) / 2, 0);
    const widgetCx = containerLeft + containerWidth - 240; // 240 corresponds to 40px right-padding + 200px half-widget
    
    const offsetX = widgetCx - (baseIconSize / 2);
    const offsetY = (height - baseIconSize) / 2;

    if (offCtx) {
        offCtx.strokeStyle = '#fff'; // Pure white for sampling
        offCtx.lineWidth = 2.5; // THICKER: Use a wide stroke to populate more coordinates
        offCtx.lineJoin = 'round';
        offCtx.translate(offsetX, offsetY);
        offCtx.scale(baseIconSize / 24, baseIconSize / 24); 
        
        // Focus Bracket SVG Path (4 Corner L-shapes) - FIXED COORDINATES FOR PERFECT SYMMETRY
        try {
          // Corner 1: (2,2) and (2,8) + (8,2)
          // Corner 2: (22,2) and (22,8) + (16,2)
          // Corner 3: (2,22) and (2,16) + (8,22)
          // Corner 4: (22,22) and (22,16) + (16,22)
          const path = new Path2D("M2 2h6 M2 2v6 M22 2h-6 M22 2v6 M2 22h6 M2 22v-6 M22 22h-6 M22 22v-6");
          offCtx.stroke(path);
        } catch (e) {
          console.warn("Path2D not supported or path invalid", e);
        }
    }

    // 2. Read the pixels to find coordinates that form the database shape
    let validCoords: {x: number, y: number}[] = [];
    try {
      const imgData = offCtx?.getImageData(0, 0, width, height).data;
      if (imgData) {
          for (let y = 0; y < height; y += 2) {
              for (let x = 0; x < width; x += 2) {
                  const alpha = imgData[(y * width + x) * 4 + 3];
                  if (alpha > 128) {
                      validCoords.push({x, y});
                  }
              }
          }
      }
    } catch (e) {
      console.error("Failed to read image data for particles", e);
    }

    // 3. Initialize Particles
    const particles: Particle[] = [];
    // White palette with varying shades to look technical and prominent
    const colors = ['#ffffff', '#f8fafc', '#f1f5f9', '#e2e8f0', '#cbd5e1']; 

    for (let i = 0; i < particleCount; i++) {
        const target = validCoords.length > 0 
           ? validCoords[Math.floor(Math.random() * validCoords.length)]
           : { x: width/2, y: height/2 };

        const scX = Math.random() * width;
        const scY = Math.random() * height;

        particles.push({
            x: scX,
            y: scY,
            tgX: target.x,
            tgY: target.y,
            scX: scX,
            scY: scY,
            vx: 0,
            vy: 0,
            size: Math.random() * 0.8 + 0.9, // More prominent: 0.9 - 1.7px
            color: colors[Math.floor(Math.random() * colors.length)],
            angle: Math.random() * Math.PI * 2,
            speed: Math.random() * 0.4 + 0.2, // Slightly faster drift base
            isRogue: Math.random() < 0.2 // 20% rogue
        });
    }

    particlesRef.current = particles;

    // 4. The Animation Engine
    const render = () => {
        if (!ctx) return;
        ctx.clearRect(0, 0, width, height);
        
        // SMOOTH FADE TRANSITION: Drift fadeFactorRef based on state
        const targetFade = canvas.dataset.assembled === 'true' ? 1 : 0.22;
        fadeFactorRef.current += (targetFade - fadeFactorRef.current) * 0.05; // Smooth 5% drift per frame

        const activeAssembled = canvas.dataset.assembled === 'true';

        particlesRef.current.forEach(p => {
            if (activeAssembled && !p.isRogue) {
                // HIGH-ENERGY ASSEMBLED STATE: Vibrating, living data stream
                p.angle += p.speed * 0.12; // FASTER: Creates a high-frequency 'hum'
                const dynamicTargetX = p.tgX + Math.cos(p.angle) * 3;
                const dynamicTargetY = p.tgY + Math.sin(p.angle) * 3;

                const dx = dynamicTargetX - p.x;
                const dy = dynamicTargetY - p.y;
                
                // POWERFUL TENSION (0.05) for a snappy, magnetic snap
                p.vx += dx * 0.05; 
                p.vy += dy * 0.05;
                
                // Lower friction (0.85) to allow more 'life' and momentum
                p.vx *= 0.85; 
                p.vy *= 0.85;

                // Speed Cap (8) to allow for the faster snap
                const speed = Math.sqrt(p.vx * p.vx + p.vy * p.vy);
                if (speed > 8) {
                    p.vx = (p.vx / speed) * 8;
                    p.vy = (p.vy / speed) * 8;
                }
            } else {
                // DEFAULT / ROGUE STATE: Gentle drift
                p.angle += p.speed * 0.01;
                const floatX = p.scX + Math.cos(p.angle) * 20;
                const floatY = p.scY + Math.sin(p.angle) * 20;
                
                const dx = floatX - p.x;
                const dy = floatY - p.y;
                
                p.vx += dx * 0.002;
                p.vy += dy * 0.002;
                p.vx *= 0.97;
                p.vy *= 0.97;
            }

            p.x += p.vx;
            p.y += p.vy;

            // DYNAMIC OPACITY: Particles are subtle when idle, but populate/brighten on hover
            ctx.fillStyle = p.color;
            const baseAlpha = p.isRogue ? 0.3 : 0.7;
            ctx.globalAlpha = baseAlpha * fadeFactorRef.current;
            
            ctx.fillRect(p.x, p.y, p.size, p.size);
            ctx.globalAlpha = 1.0;
        });

        animationRef.current = requestAnimationFrame(render);
    };

    render();

    return () => {
        if (animationRef.current) cancelAnimationFrame(animationRef.current);
    };
  }, [width, height, particleCount]);

  return (
    <div style={{ position: 'absolute', top: 0, left: 0, right: 0, bottom: 0 }}>
        <canvas
        ref={canvasRef}
        width={width}
        height={height}
        data-assembled={isAssembled}
        onMouseEnter={() => setInternalHover(true)}
        onMouseLeave={() => setInternalHover(false)}
        style={{
            background: 'transparent',
            display: 'block'
        }}
        />
    </div>
  );
};
