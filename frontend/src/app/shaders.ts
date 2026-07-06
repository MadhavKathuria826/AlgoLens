import * as THREE from 'three';
import { shaderMaterial } from '@react-three/drei';
import { extend } from '@react-three/fiber';

// Background Shader using Simplex Noise and Domain Warping
export const BackgroundShaderMaterial = shaderMaterial(
  {
    uTime: 0,
    uScroll: 0,
    uCursor: new THREE.Vector2(0.5, 0.5),
    uColorTeal: new THREE.Color('#00e5ff'),
    uColorCyan: new THREE.Color('#09fbd3'),
    uColorViolet: new THREE.Color('#fe53bb'),
    uColorBlack: new THREE.Color('#020204'),
  },
  // Vertex Shader
  `
    varying vec2 vUv;
    void main() {
      vUv = uv;
      gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
    }
  `,
  // Fragment Shader
  `
    uniform float uTime;
    uniform float uScroll;
    uniform vec2 uCursor;
    uniform vec3 uColorTeal;
    uniform vec3 uColorCyan;
    uniform vec3 uColorViolet;
    uniform vec3 uColorBlack;
    
    varying vec2 vUv;
    
    // Simplex 2D noise
    vec3 permute(vec3 x) { return mod(((x*34.0)+1.0)*x, 289.0); }
    float snoise(vec2 v){
      const vec4 C = vec4(0.211324865405187, 0.366025403784439, -0.577350269189626, 0.024390243902439);
      vec2 i  = floor(v + dot(v, C.yy) );
      vec2 x0 = v -   i + dot(i, C.xx);
      vec2 i1;
      i1 = (x0.x > x0.y) ? vec2(1.0, 0.0) : vec2(0.0, 1.0);
      vec4 x12 = x0.xyxy + C.xxzz;
      x12.xy -= i1;
      i = mod(i, 289.0);
      vec3 p = permute( permute( i.y + vec3(0.0, i1.y, 1.0 )) + i.x + vec3(0.0, i1.x, 1.0 ));
      vec3 m = max(0.5 - vec3(dot(x0,x0), dot(x12.xy,x12.xy), dot(x12.zw,x12.zw)), 0.0);
      m = m*m;
      m = m*m;
      vec3 x = 2.0 * fract(p * C.www) - 1.0;
      vec3 h = abs(x) - 0.5;
      vec3 ox = floor(x + 0.5);
      vec3 a0 = x - ox;
      m *= 1.79284291400159 - 0.85373472095314 * ( a0*a0 + h*h );
      vec3 g;
      g.x  = a0.x  * x0.x  + h.x  * x0.y;
      g.yz = a0.yz * x12.xz + h.yz * x12.yw;
      return 130.0 * dot(m, g);
    }

    void main() {
      // Base UV
      vec2 uv = vUv;
      
      // Cursor distortion (gravitational pull)
      float distToCursor = distance(uv, uCursor);
      vec2 dirToCursor = distToCursor > 0.0001 ? normalize(uCursor - uv) : vec2(0.0);
      float pull = smoothstep(0.5, 0.0, distToCursor) * 0.1;
      uv += dirToCursor * pull;
      
      // Domain warping based on time and scroll (Reduced from 3 to 2 passes for performance)
      float t = uTime * 0.2 + uScroll * 2.0;
      vec2 q = vec2(0.);
      q.x = snoise(uv * 2.0 + vec2(t, t));
      q.y = snoise(uv * 2.0 + vec2(t * 1.5, t * 1.5));
      
      float n = snoise(uv * 2.0 + q);
      
      // Map noise to colors
      // Scroll shifts the color weighting
      vec3 baseColor = mix(uColorBlack, uColorTeal, smoothstep(-1.0, 1.0, n));
      baseColor = mix(baseColor, uColorCyan, smoothstep(0.0, 1.0, q.x) * 0.5);
      
      // Inject Violet based on scroll progress to increase energy near bottom
      float violetEnergy = smoothstep(0.0, 1.0, uScroll) * smoothstep(-0.5, 1.0, q.y);
      baseColor = mix(baseColor, uColorViolet, violetEnergy * 0.6);
      
      // Add subtle vignette
      float vignette = smoothstep(1.5, 0.5, length(vUv - 0.5) * 2.0);
      baseColor *= vignette;

      // Darken overall to keep it a background (Minimalistic baseline)
      baseColor *= 0.3;
      
      gl_FragColor = vec4(baseColor, 1.0);
    }
  `
);

extend({ BackgroundShaderMaterial });
