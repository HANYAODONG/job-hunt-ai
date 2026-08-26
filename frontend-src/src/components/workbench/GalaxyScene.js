import React, { useEffect, useRef, useState } from 'react';
import gsap from 'gsap';
import * as THREE from 'three';
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js';
import { CSS2DObject, CSS2DRenderer } from 'three/examples/jsm/renderers/CSS2DRenderer.js';

const ARM_COLORS = [
  '#ef7baa', // 算法
  '#59d3c6', // 大模型
  '#aa8cf3', // 后端
  '#dfb563', // 前端
  '#f28b8b', // 数据
  '#7bc8f0', // 运维
  '#f5a623', // 安全
  '#7ed3a8', // 硬件
  '#d4a0d4', // 测试
  '#a0a0a0', // 其他
];

// 扩展半径数组，支持 10 个大类
const DOMAIN_RADII = [3.2, 3.7, 4.05, 3.45, 3.0, 3.8, 4.2, 3.6, 3.3, 3.9];

const OVERVIEW_CAMERA = { x: 0, y: 4.65, z: 11.4 };

const seededRandom = (seed) => {
  let value = seed >>> 0;
  return () => {
    value = (value * 1664525 + 1013904223) >>> 0;
    return value / 4294967296;
  };
};

const createGlowTexture = (color) => {
  const canvas = document.createElement('canvas');
  canvas.width = 256;
  canvas.height = 256;
  const context = canvas.getContext('2d');
  const rgb = new THREE.Color(color);
  const red = Math.round(rgb.r * 255);
  const green = Math.round(rgb.g * 255);
  const blue = Math.round(rgb.b * 255);
  const gradient = context.createRadialGradient(128, 128, 2, 128, 128, 126);
  gradient.addColorStop(0, 'rgba(255, 250, 232, 1)');
  gradient.addColorStop(0.08, `rgba(${red}, ${green}, ${blue}, .98)`);
  gradient.addColorStop(0.28, `rgba(${red}, ${green}, ${blue}, .42)`);
  gradient.addColorStop(0.62, `rgba(${red}, ${green}, ${blue}, .1)`);
  gradient.addColorStop(1, `rgba(${red}, ${green}, ${blue}, 0)`);
  context.fillStyle = gradient;
  context.fillRect(0, 0, 256, 256);
  const texture = new THREE.CanvasTexture(canvas);
  texture.colorSpace = THREE.SRGBColorSpace;
  return texture;
};

const createPointMaterial = (pixelRatio, opacity = 1, profile = 'galaxy') => {
  const isBackground = profile === 'background';
  const pointScale = isBackground ? 11 : 7.6;
  const pointScaleLiteral = pointScale.toFixed(1);
  const shimmerBase = isBackground ? 0.985 : 0.91;
  const shimmerRange = isBackground ? 0.015 : 0.09;
  const coreRadius = isBackground ? 0.34 : 0.28;

  return new THREE.ShaderMaterial({
  transparent: true,
  depthWrite: false,
  blending: THREE.AdditiveBlending,
  vertexColors: true,
  uniforms: {
    uPixelRatio: { value: pixelRatio },
    uTime: { value: 0 },
    uOpacity: { value: opacity },
  },
  vertexShader: `
    attribute float aSize;
    attribute float aPhase;
    uniform float uPixelRatio;
    uniform float uTime;
    varying vec3 vColor;
    varying float vAlpha;

    void main() {
      vec4 modelPosition = modelMatrix * vec4(position, 1.0);
      vec4 viewPosition = viewMatrix * modelPosition;
      float shimmer = ${shimmerBase} + ${shimmerRange} * sin(uTime * 0.7 + aPhase);
      vColor = color;
      vAlpha = shimmer;
      gl_Position = projectionMatrix * viewPosition;
      gl_PointSize = aSize * uPixelRatio * (${pointScaleLiteral} / max(1.0, -viewPosition.z));
    }
  `,
  fragmentShader: `
    uniform float uOpacity;
    varying vec3 vColor;
    varying float vAlpha;

    void main() {
      float radial = length(gl_PointCoord - vec2(0.5));
      float alpha = 1.0 - smoothstep(${coreRadius}, 0.5, radial);
      gl_FragColor = vec4(vColor, alpha * vAlpha * uOpacity);
    }
  `,
  });
};

const createStarMaterial = (color) => new THREE.ShaderMaterial({
  uniforms: {
    uColor: { value: new THREE.Color(color) },
    uTime: { value: 0 },
  },
  vertexShader: `
    varying vec3 vNormal;
    varying vec3 vPosition;
    varying vec3 vViewDirection;

    void main() {
      vec4 modelPosition = modelMatrix * vec4(position, 1.0);
      vec4 viewPosition = viewMatrix * modelPosition;
      vNormal = normalize(normalMatrix * normal);
      vPosition = position;
      vViewDirection = normalize(-viewPosition.xyz);
      gl_Position = projectionMatrix * viewPosition;
    }
  `,
  fragmentShader: `
    uniform vec3 uColor;
    uniform float uTime;
    varying vec3 vNormal;
    varying vec3 vPosition;
    varying vec3 vViewDirection;

    void main() {
      float facing = max(0.0, dot(normalize(vNormal), normalize(vViewDirection)));
      float rim = pow(1.0 - facing, 2.1);
      float bands = sin(vPosition.x * 19.0 + uTime * 1.25) * sin(vPosition.y * 23.0 - uTime * 0.9);
      float activity = 0.5 + 0.5 * bands;
      vec3 warmCore = vec3(1.0, 0.9, 0.68);
      vec3 surface = mix(uColor * 0.7, warmCore, facing * 0.58 + activity * 0.11);
      surface += uColor * rim * 1.25;
      gl_FragColor = vec4(surface, 1.0);
    }
  `,
});

const createGalaxyGeometry = () => {
  const count = 36000;
  const positions = new Float32Array(count * 3);
  const colors = new Float32Array(count * 3);
  const sizes = new Float32Array(count);
  const phases = new Float32Array(count);
  const random = seededRandom(20260727);
  const coreColor = new THREE.Color('#e8d7af');
  const discColor = new THREE.Color('#d9e6f0');
  const outerColor = new THREE.Color('#a9c3da');

  const normal = () => {
    const u = Math.max(random(), 0.0001);
    const v = random();
    return Math.sqrt(-2 * Math.log(u)) * Math.cos(Math.PI * 2 * v);
  };

  for (let index = 0; index < count; index += 1) {
    const i3 = index * 3;
    const isCore = index < count * 0.18;
    const isInterArm = !isCore && random() < 0.34;
    let radius;
    let pointColor;

    if (isCore) {
      radius = Math.pow(random(), 1.72) * 1.9;
      const theta = random() * Math.PI * 2;
      const coreRadius = radius * (0.78 + random() * 0.28);
      positions[i3] = Math.cos(theta) * coreRadius;
      positions[i3 + 1] = normal() * (0.04 + coreRadius * 0.12);
      positions[i3 + 2] = Math.sin(theta) * coreRadius * 0.78;
      pointColor = coreColor.clone().lerp(discColor, radius / 2.35);
    } else {
      radius = 0.5 + Math.pow(random(), 0.66) * 5.9;
      const branch = Math.floor(random() * 4);
      const baseAngle = branch / 4 * Math.PI * 2 + 3.35 * Math.log(radius + 0.7);
      const dustSide = random() < 0.5 ? -1 : 1;
      const dustOffset = 0.042 + radius * 0.009;
      const armAngle = isInterArm
        ? random() * Math.PI * 2
        : baseAngle + dustSide * dustOffset + normal() * (0.055 + radius * 0.04);
      const radialOffset = normal() * (isInterArm ? 0.16 + radius * 0.064 : 0.05 + radius * 0.036);
      const orbitRadius = radius + radialOffset;
      const taper = Math.max(0, 1 - radius / 6.45);
      const discHeight = 0.065 + 0.16 * Math.pow(taper, 1.25);
      positions[i3] = Math.cos(armAngle) * orbitRadius;
      positions[i3 + 1] = normal() * discHeight + Math.sin(armAngle * 2 + radius) * discHeight * 0.14;
      positions[i3 + 2] = Math.sin(armAngle) * orbitRadius;
      pointColor = discColor.clone().lerp(outerColor, Math.min(1, radius / 6.4));
      if (isInterArm) pointColor.multiplyScalar(0.56 + random() * 0.14);
    }

    colors[i3] = pointColor.r;
    colors[i3 + 1] = pointColor.g;
    colors[i3 + 2] = pointColor.b;
    sizes[index] = index % 311 === 0
      ? 6.4
      : index % 47 === 0
        ? 4.1
        : (isCore ? 1.5 : isInterArm ? 0.95 : 1.45) + random() * (isCore ? 0.95 : isInterArm ? 0.75 : 1.15);
    phases[index] = random() * Math.PI * 2;
  }

  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute('position', new THREE.BufferAttribute(positions, 3));
  geometry.setAttribute('color', new THREE.BufferAttribute(colors, 3));
  geometry.setAttribute('aSize', new THREE.BufferAttribute(sizes, 1));
  geometry.setAttribute('aPhase', new THREE.BufferAttribute(phases, 1));
  return geometry;
};

const createHaloGeometry = () => {
  const count = 1400;
  const positions = new Float32Array(count * 3);
  const colors = new Float32Array(count * 3);
  const sizes = new Float32Array(count);
  const phases = new Float32Array(count);
  const random = seededRandom(20260803);
  const haloColor = new THREE.Color('#b6c0d0');

  for (let index = 0; index < count; index += 1) {
    const i3 = index * 3;
    const radius = 4.9 + Math.pow(random(), 0.55) * 4.6;
    const theta = random() * Math.PI * 2;
    const phi = Math.acos(2 * random() - 1);
    positions[i3] = radius * Math.sin(phi) * Math.cos(theta);
    positions[i3 + 1] = radius * Math.cos(phi) * 0.86;
    positions[i3 + 2] = radius * Math.sin(phi) * Math.sin(theta);
    const brightness = 0.2 + random() * 0.22;
    colors[i3] = haloColor.r * brightness;
    colors[i3 + 1] = haloColor.g * brightness;
    colors[i3 + 2] = haloColor.b * brightness;
    sizes[index] = 0.55 + random() * 0.85;
    phases[index] = random() * Math.PI * 2;
  }

  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute('position', new THREE.BufferAttribute(positions, 3));
  geometry.setAttribute('color', new THREE.BufferAttribute(colors, 3));
  geometry.setAttribute('aSize', new THREE.BufferAttribute(sizes, 1));
  geometry.setAttribute('aPhase', new THREE.BufferAttribute(phases, 1));
  return geometry;
};

const createBackgroundGeometry = () => {
  const count = 3200;
  const positions = new Float32Array(count * 3);
  const colors = new Float32Array(count * 3);
  const sizes = new Float32Array(count);
  const phases = new Float32Array(count);
  const random = seededRandom(3652026);
  const brightnessRandom = seededRandom(20260802);
  const palette = ['#dbe5e7', '#d5dde4', '#e1e4e8', '#e6dfcf'];

  for (let index = 0; index < count; index += 1) {
    const i3 = index * 3;
    const radius = 38 + Math.pow(random(), 0.72) * 18;
    const theta = random() * Math.PI * 2;
    const phi = Math.acos(2 * random() - 1);
    positions[i3] = radius * Math.sin(phi) * Math.cos(theta);
    positions[i3 + 1] = radius * Math.cos(phi);
    positions[i3 + 2] = radius * Math.sin(phi) * Math.sin(theta);
    const color = new THREE.Color(palette[index % palette.length]);
    color.multiplyScalar(brightnessRandom() < 0.3 ? 1.55 : 0.78);
    colors[i3] = color.r;
    colors[i3 + 1] = color.g;
    colors[i3 + 2] = color.b;
    sizes[index] = index % 193 === 0 ? 18 : index % 29 === 0 ? 13 : 9.3 + random() * 4.8;
    phases[index] = random() * Math.PI * 2;
  }

  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute('position', new THREE.BufferAttribute(positions, 3));
  geometry.setAttribute('color', new THREE.BufferAttribute(colors, 3));
  geometry.setAttribute('aSize', new THREE.BufferAttribute(sizes, 1));
  geometry.setAttribute('aPhase', new THREE.BufferAttribute(phases, 1));
  return geometry;
};

// Keep overview labels readable when the taxonomy has more categories than one orbit can hold.
const anchorForDomain = (index, totalDomains = 10) => {
  if (totalDomains > ARM_COLORS.length) {
    const innerCount = Math.ceil(totalDomains / 2);
    const isOuterRing = index >= innerCount;
    const ringCount = isOuterRing ? totalDomains - innerCount : innerCount;
    const ringIndex = isOuterRing ? index - innerCount : index;
    const radius = isOuterRing ? 5.25 : 3.25;
    const angleOffset = isOuterRing ? Math.PI / ringCount : 0;
    const angle = (ringIndex / ringCount) * Math.PI * 2 + angleOffset;
    return new THREE.Vector3(Math.cos(angle) * radius, 0, Math.sin(angle) * radius);
  }
  const radius = DOMAIN_RADII[index % DOMAIN_RADII.length] || 3.5;
  const angle = (index / totalDomains) * Math.PI * 2 + radius * 1.16;
  return new THREE.Vector3(Math.cos(angle) * radius, 0, Math.sin(angle) * radius);
};

const createLabel = (node, className, eyebrow) => {
  const element = document.createElement('div');
  element.className = `galaxy-object-label ${className}`;
  element.dataset.nodeId = node.id;
  if (node.is_single_role) element.classList.add('is-single-role');
  if (eyebrow) {
    const level = document.createElement('span');
    level.textContent = eyebrow;
    element.appendChild(level);
  }
  const label = document.createElement('strong');
  label.textContent = node.label;
  element.appendChild(label);
  const meta = document.createElement('small');
  meta.textContent = node.is_single_role && node.taxonomy_status
    ? `${node.count} 岗位 · ${node.taxonomy_status}`
    : `${node.count} 岗位 · ${node.growth}`;
  element.appendChild(meta);
  return new CSS2DObject(element);
};

const createOrbit = (radius, color, opacity = 0.28) => {
  const points = Array.from({ length: 160 }, (_, index) => {
    const angle = index / 160 * Math.PI * 2;
    return new THREE.Vector3(Math.cos(angle) * radius, 0, Math.sin(angle) * radius);
  });
  const geometry = new THREE.BufferGeometry().setFromPoints(points);
  const material = new THREE.LineBasicMaterial({ color, transparent: true, opacity });
  return new THREE.LineLoop(geometry, material);
};

const addInteractiveStar = ({ parent, node, color, glowTexture, position, size, labelClass, eyebrow, interactiveObjects, nodeObjects, starMaterials, starMaterialCache }) => {
  const group = new THREE.Group();
  group.position.copy(position);
  parent.add(group);

  const materialKey = new THREE.Color(color).getHexString();
  let starMaterial = starMaterialCache.get(materialKey);
  if (!starMaterial) {
    starMaterial = createStarMaterial(color);
    starMaterialCache.set(materialKey, starMaterial);
    starMaterials.push(starMaterial);
  }
  const star = new THREE.Mesh(
    new THREE.IcosahedronGeometry(size, size > 0.1 ? 4 : 2),
    starMaterial,
  );
  star.userData = { nodeId: node.id, baseScale: 1, nodeType: node.type };
  group.add(star);

  const glow = new THREE.Sprite(new THREE.SpriteMaterial({ map: glowTexture, transparent: true, blending: THREE.AdditiveBlending, depthWrite: false }));
  const glowScale = size * 7.4;
  glow.scale.set(glowScale, glowScale, 1);
  glow.userData.baseScale = glowScale;
  group.add(glow);

  const hit = new THREE.Mesh(
    new THREE.SphereGeometry(size * 2.3, 16, 16),
    new THREE.MeshBasicMaterial({ transparent: true, opacity: 0, depthWrite: false }),
  );
  hit.userData = { nodeId: node.id, baseScale: 1, nodeType: node.type, visual: star };
  group.add(hit);
  interactiveObjects.push(hit);
  const nodeObject = { group, visual: star, glow };
  nodeObjects.set(node.id, [...(nodeObjects.get(node.id) || []), nodeObject]);

  if (labelClass) {
    const label = createLabel(node, labelClass, eyebrow);
    label.position.set(0, labelClass.includes('galaxy-system-star-label') ? -0.58 : size * 2.1, 0);
    group.add(label);
  }

  return group;
};

const buildDomainSystem = ({ domain, domainIndex, color, glowTexture, interactiveObjects, nodeObjects, animatedBodies, resources, starMaterials, starMaterialCache }) => {
  const system = new THREE.Group();
  system.name = `domain-system-${domain.id}`;
  system.visible = false;
  system.scale.setScalar(0.001);
  system.rotation.x = 0.08;

  const center = addInteractiveStar({
    parent: system,
    node: domain,
    color,
    glowTexture,
    position: new THREE.Vector3(),
    size: 0.16,
    labelClass: 'galaxy-system-star-label',
    eyebrow: '一级分类 · 恒星',
    interactiveObjects,
    nodeObjects,
    starMaterials,
    starMaterialCache,
  });
  system.userData.centralGlow = center.children.find((child) => child.isSprite);

  (domain.children || []).forEach((family, familyIndex) => {
    const orbitRadius = 1.15 + familyIndex * 0.82;
    const orbit = createOrbit(orbitRadius, color, 0.22 + familyIndex * 0.035);
    system.add(orbit);
    resources.push(orbit.geometry, orbit.material);

    const familyAngle = 0.55 + familyIndex * 2.22 + domainIndex * 0.34;
    const familyPivot = new THREE.Group();
    system.add(familyPivot);
    const familyColor = new THREE.Color(color).lerp(new THREE.Color('#f0d7ad'), 0.08 + familyIndex * 0.08).getStyle();
    addInteractiveStar({
      parent: familyPivot,
      node: family,
      color: familyColor,
      glowTexture,
      position: new THREE.Vector3(Math.cos(familyAngle) * orbitRadius, 0, Math.sin(familyAngle) * orbitRadius),
      size: 0.1 + familyIndex * 0.012,
      labelClass: 'galaxy-planet-label',
      eyebrow: '岗位方向',
      interactiveObjects,
      nodeObjects,
      starMaterials,
      starMaterialCache,
    });
    animatedBodies.push({ object: familyPivot, speed: 0.035 - familyIndex * 0.006, phase: 0 });
  });

  return system;
};

const buildFamilySystem = ({ family, familyIndex, color, glowTexture, interactiveObjects, nodeObjects, animatedBodies, resources, starMaterials, starMaterialCache }) => {
  const system = new THREE.Group();
  system.name = `family-system-${family.id}`;
  system.visible = false;
  system.scale.setScalar(0.001);
  system.rotation.set(0.12, 0, familyIndex % 2 ? 0.13 : -0.13);

  const familyColor = new THREE.Color(color).lerp(new THREE.Color('#f0d7ad'), 0.12 + familyIndex * 0.07).getStyle();
  const center = addInteractiveStar({
    parent: system,
    node: family,
    color: familyColor,
    glowTexture,
    position: new THREE.Vector3(),
    size: 0.075,
    labelClass: 'galaxy-system-star-label galaxy-family-center-label',
    eyebrow: '岗位方向 · 中心行星',
    interactiveObjects,
    nodeObjects,
    starMaterials,
    starMaterialCache,
  });
  system.userData.centralGlow = center.children.find((child) => child.isSprite);

  const roles = family.children || [];
  const roleCount = Math.max(roles.length, 1);
  roles.forEach((role, roleIndex) => {
    const orbitRadius = 1.05 + roleIndex * 0.64;
    const orbitPlane = new THREE.Group();
    orbitPlane.rotation.set(
      (roleIndex - (roleCount - 1) / 2) * 0.14,
      (roleIndex % 2 ? 1 : -1) * (0.08 + roleIndex * 0.035),
      (roleIndex % 2 ? 1 : -1) * (0.16 + roleIndex * 0.035),
    );
    system.add(orbitPlane);

    const orbit = createOrbit(orbitRadius, familyColor, 0.2 + roleIndex * 0.035);
    orbitPlane.add(orbit);
    resources.push(orbit.geometry, orbit.material);

    const rolePivot = new THREE.Group();
    orbitPlane.add(rolePivot);
    const roleAngle = 0.45 + (roleIndex / roleCount) * Math.PI * 2;
    addInteractiveStar({
      parent: rolePivot,
      node: role,
      color: familyColor,
      glowTexture,
      position: new THREE.Vector3(Math.cos(roleAngle) * orbitRadius, 0, Math.sin(roleAngle) * orbitRadius),
      size: 0.038 + Math.min(roleIndex, 5) * 0.003,
      labelClass: 'galaxy-satellite-label',
      eyebrow: '',
      interactiveObjects,
      nodeObjects,
      starMaterials,
      starMaterialCache,
    });
    animatedBodies.push({ object: rolePivot, speed: 0.07 + roleIndex * 0.018, phase: roleAngle });
  });

  return system;
};

const GalaxyScene = ({ tree, mode, focusDomainId, focusFamilyId, selectedId, onNodeSelect }) => {
  const mountRef = useRef(null);
  const engineRef = useRef(null);
  const [engineVersion, setEngineVersion] = useState(0);
  const callbackRef = useRef(onNodeSelect);
  const modeRef = useRef(mode);
  callbackRef.current = onNodeSelect;
  modeRef.current = mode;

  useEffect(() => {
    const mount = mountRef.current;
    if (!mount || !tree) return undefined;

    const pixelRatio = Math.min(window.devicePixelRatio || 1, 1.35);
    const renderer = new THREE.WebGLRenderer({ alpha: true, antialias: pixelRatio <= 1.15, powerPreference: 'high-performance' });
    renderer.setPixelRatio(pixelRatio);
    renderer.setClearColor(0x000000, 0);
    renderer.outputColorSpace = THREE.SRGBColorSpace;
    renderer.toneMapping = THREE.ACESFilmicToneMapping;
    renderer.toneMappingExposure = 1.08;
    renderer.domElement.setAttribute('aria-label', '三维岗位银河');
    mount.appendChild(renderer.domElement);

    const labelRenderer = new CSS2DRenderer();
    labelRenderer.domElement.className = 'graph-label-layer';
    mount.appendChild(labelRenderer.domElement);

    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(46, 1, 0.05, 100);
    camera.position.set(OVERVIEW_CAMERA.x, OVERVIEW_CAMERA.y, OVERVIEW_CAMERA.z);
    const controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;
    controls.dampingFactor = 0.045;
    controls.enablePan = false;
    controls.minDistance = 4.2;
    controls.maxDistance = 16;
    controls.target.set(0, 0, 0);

    const resources = [];
    const glowTextures = ARM_COLORS.map(createGlowTexture);
    resources.push(...glowTextures);
    const interactiveObjects = [];
    const nodeObjects = new Map();
    const animatedBodies = [];
    const starMaterials = [];
    const starMaterialCache = new Map();
    const domainAnchors = new Map();
    const domainSystems = new Map();
    const familySystems = new Map();
    const familyDescriptors = new Map();
    const systems = [];

    const backgroundGeometry = createBackgroundGeometry();
    const backgroundMaterial = createPointMaterial(pixelRatio, 0.92, 'background');
    const background = new THREE.Points(backgroundGeometry, backgroundMaterial);
    scene.add(background);
    resources.push(backgroundGeometry, backgroundMaterial);

    const galaxyGeometry = createGalaxyGeometry();
    const galaxyMaterial = createPointMaterial(pixelRatio, 1);
    const galaxyGroup = new THREE.Group();
    const halo = new THREE.Points(createHaloGeometry(), galaxyMaterial);
    const galaxy = new THREE.Points(galaxyGeometry, galaxyMaterial);
    galaxyGroup.add(halo);
    galaxyGroup.add(galaxy);
    scene.add(galaxyGroup);
    resources.push(halo.geometry, galaxyGeometry, galaxyMaterial);

    // 计算总大类数
    const totalDomains = (tree.children || []).length;

    (tree.children || []).forEach((domain, index) => {
      const color = ARM_COLORS[index % ARM_COLORS.length];
      const anchor = anchorForDomain(index, totalDomains);
      const starGroup = addInteractiveStar({
        parent: galaxyGroup,
      node: domain,
      color,
      glowTexture: glowTextures[index % glowTextures.length],
        position: anchor,
        size: 0.065,
        labelClass: 'galaxy-domain-label',
        eyebrow: '一级分类',
        interactiveObjects,
        nodeObjects,
        starMaterials,
        starMaterialCache,
      });
      domainAnchors.set(domain.id, starGroup);
      const domainSystem = buildDomainSystem({ domain, domainIndex: index, color, glowTexture: glowTextures[index % glowTextures.length], interactiveObjects, nodeObjects, animatedBodies, resources, starMaterials, starMaterialCache });
      domainSystems.set(domain.id, domainSystem);
      systems.push(domainSystem);
      scene.add(domainSystem);
      (domain.children || []).forEach((family, familyIndex) => {
        familyDescriptors.set(family.id, {
          family,
          familyIndex,
          color,
          glowTexture: glowTextures[index % glowTextures.length],
        });
      });
    });

    const ensureFamilySystem = (familyId) => {
      if (familySystems.has(familyId)) return familySystems.get(familyId);
      const descriptor = familyDescriptors.get(familyId);
      if (!descriptor) return null;
      const familySystem = buildFamilySystem({
        ...descriptor,
        interactiveObjects,
        nodeObjects,
        animatedBodies,
        resources,
        starMaterials,
        starMaterialCache,
      });
      familySystems.set(familyId, familySystem);
      systems.push(familySystem);
      scene.add(familySystem);
      return familySystem;
    };

    const raycaster = new THREE.Raycaster();
    const pointer = new THREE.Vector2();
    let hovered = null;
    const setHover = (object) => {
      if (hovered === object) return;
      if (hovered?.userData.visual) {
        hovered.userData.visual.scale.setScalar(hovered.userData.visual.userData.selected ? 1.42 : 1);
        hovered.userData.visual.parent?.children?.find((child) => child.isCSS2DObject)?.element?.classList.remove('is-hovered');
      }
      hovered = object;
      if (hovered?.userData.visual) {
        hovered.userData.visual.scale.setScalar(1.32);
        hovered.userData.visual.parent?.children?.find((child) => child.isCSS2DObject)?.element?.classList.add('is-hovered');
      }
      renderer.domElement.style.cursor = hovered ? 'pointer' : 'grab';
    };
    const isWorldVisible = (object) => {
      let current = object;
      while (current) {
        if (!current.visible) return false;
        current = current.parent;
      }
      return true;
    };
    const pick = (event) => {
      const rect = renderer.domElement.getBoundingClientRect();
      pointer.x = ((event.clientX - rect.left) / rect.width) * 2 - 1;
      pointer.y = -((event.clientY - rect.top) / rect.height) * 2 + 1;
      raycaster.setFromCamera(pointer, camera);
      return raycaster.intersectObjects(interactiveObjects, false).find((hit) => isWorldVisible(hit.object))?.object || null;
    };
    const onPointerMove = (event) => setHover(pick(event));
    const onPointerLeave = () => setHover(null);
    const onClick = (event) => {
      const object = pick(event);
      if (object?.userData.nodeId) callbackRef.current?.(object.userData.nodeId);
    };
    renderer.domElement.addEventListener('pointermove', onPointerMove);
    renderer.domElement.addEventListener('pointerleave', onPointerLeave);
    renderer.domElement.addEventListener('click', onClick);

    const resize = () => {
      const { width, height } = mount.getBoundingClientRect();
      if (!width || !height) return;
      camera.aspect = width / height;
      camera.updateProjectionMatrix();
      renderer.setSize(width, height, false);
      labelRenderer.setSize(width, height);
    };
    const observer = new ResizeObserver(resize);
    observer.observe(mount);
    resize();

    const clock = new THREE.Clock();
    const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    let frameId;
    let isIntersecting = true;
    let isDocumentVisible = !document.hidden;
    const scheduleFrame = () => {
      if (!frameId && isIntersecting && isDocumentVisible) frameId = window.requestAnimationFrame(renderFrame);
    };
    const renderFrame = () => {
      frameId = null;
      if (!isIntersecting || !isDocumentVisible) return;
      const elapsed = clock.getElapsedTime();
      galaxyMaterial.uniforms.uTime.value = elapsed;
      backgroundMaterial.uniforms.uTime.value = elapsed * 0.42;
      starMaterials.forEach((material) => { material.uniforms.uTime.value = elapsed; });
      if (modeRef.current === 'overview' && !reduceMotion) galaxyGroup.rotation.y += 0.00022;
      if (!reduceMotion) {
        background.rotation.y = elapsed * 0.0025;
        background.rotation.x = Math.sin(elapsed * 0.025) * 0.018;
      }
      animatedBodies.forEach((body) => { body.object.rotation.y = body.phase + elapsed * body.speed; });
      systems.forEach((system) => {
        if (system.visible) {
          const centralGlow = system.userData.centralGlow;
          if (centralGlow) {
            const baseScale = centralGlow.userData.baseScale || 1;
            centralGlow.scale.setScalar(baseScale * (1 + Math.sin(elapsed * 1.2) * 0.035));
          }
        }
      });
      controls.update();
      renderer.render(scene, camera);
      labelRenderer.render(scene, camera);
      scheduleFrame();
    };
    const onVisibilityChange = () => {
      isDocumentVisible = !document.hidden;
      scheduleFrame();
    };
    const visibilityObserver = 'IntersectionObserver' in window
      ? new IntersectionObserver(([entry]) => {
        isIntersecting = entry.isIntersecting;
        scheduleFrame();
      }, { threshold: 0.01 })
      : null;
    visibilityObserver?.observe(mount);
    document.addEventListener('visibilitychange', onVisibilityChange);
    renderFrame();

    engineRef.current = {
      camera,
      controls,
      galaxyGroup,
      galaxyMaterial,
      backgroundMaterial,
      domainAnchors,
      domainSystems,
      ensureFamilySystem,
      systems,
      nodeObjects,
      currentSystem: null,
      reduceMotion,
    };
    setEngineVersion((version) => version + 1);

    return () => {
      observer.disconnect();
      visibilityObserver?.disconnect();
      document.removeEventListener('visibilitychange', onVisibilityChange);
      window.cancelAnimationFrame(frameId);
      renderer.domElement.removeEventListener('pointermove', onPointerMove);
      renderer.domElement.removeEventListener('pointerleave', onPointerLeave);
      renderer.domElement.removeEventListener('click', onClick);
      controls.dispose();
      resources.forEach((resource) => resource.dispose?.());
      nodeObjects.forEach((objects) => {
        objects.forEach(({ group }) => group.traverse((child) => {
          child.geometry?.dispose?.();
          child.material?.dispose?.();
        }));
      });
      renderer.dispose();
      renderer.domElement.remove();
      labelRenderer.domElement.remove();
      engineRef.current = null;
    };
  }, [tree]);

  useEffect(() => {
    const engine = engineRef.current;
    if (!engine) return undefined;
    const {
      camera,
      controls,
      galaxyGroup,
      galaxyMaterial,
      backgroundMaterial,
      domainAnchors,
      domainSystems,
      ensureFamilySystem,
      systems,
      reduceMotion,
    } = engine;
    const motionScale = reduceMotion ? 0 : 1;
    const timeline = gsap.timeline({ defaults: { ease: 'power2.inOut' } });
    const allSystems = systems;
    const previousSystem = engine.currentSystem;

    const beginTransition = () => {
      controls.enabled = false;
      controls.enableDamping = false;
      controls.minDistance = 0.05;
      controls.maxDistance = 100;
    };
    const finishTransition = ({ minDistance, maxDistance, currentSystem }) => {
      controls.minDistance = minDistance;
      controls.maxDistance = maxDistance;
      controls.enableDamping = true;
      controls.enabled = true;
      engine.currentSystem = currentSystem;
      controls.update();
    };

    if (mode === 'overview' || !focusDomainId) {
      domainAnchors.forEach((anchor) => { anchor.visible = true; });
      allSystems.forEach((system) => {
        if (system !== previousSystem) {
          system.visible = false;
          system.scale.setScalar(0.001);
        }
      });
      if (!previousSystem) {
        galaxyGroup.visible = true;
        galaxyGroup.scale.setScalar(1);
        galaxyMaterial.uniforms.uOpacity.value = 1;
        backgroundMaterial.uniforms.uOpacity.value = 0.8;
        controls.minDistance = 4.2;
        controls.maxDistance = 16;
        controls.enableDamping = true;
        controls.enabled = true;
        return undefined;
      }
      beginTransition();
      timeline.addLabel('systemOut');
      if (previousSystem) {
        timeline.to(previousSystem.scale, {
          x: 0.001,
          y: 0.001,
          z: 0.001,
          duration: 0.28 * motionScale,
          ease: 'power2.in',
        }, 'systemOut');
      }
      timeline
        .addLabel('galaxyReturn')
        .call(() => {
          if (previousSystem) previousSystem.visible = false;
          galaxyGroup.visible = true;
        }, [], 'galaxyReturn')
        .to(galaxyMaterial.uniforms.uOpacity, { value: 1, duration: 0.38 * motionScale }, 'galaxyReturn')
        .to(backgroundMaterial.uniforms.uOpacity, { value: 0.8, duration: 0.38 * motionScale }, 'galaxyReturn')
        .to(galaxyGroup.scale, { x: 1, y: 1, z: 1, duration: 0.68 * motionScale }, 'galaxyReturn')
        .to(camera.position, { ...OVERVIEW_CAMERA, duration: 0.68 * motionScale }, 'galaxyReturn')
        .to(controls.target, {
          x: 0,
          y: 0,
          z: 0,
          duration: 0.68 * motionScale,
          onComplete: () => finishTransition({ minDistance: 4.2, maxDistance: 16, currentSystem: null }),
        }, 'galaxyReturn');
      return () => timeline.kill();
    }

    const anchorObject = domainAnchors.get(focusDomainId);
    const targetSystem = mode === 'family'
      ? ensureFamilySystem(focusFamilyId)
      : domainSystems.get(focusDomainId);
    if (!anchorObject || !targetSystem) return undefined;

    const anchor = anchorObject.getWorldPosition(new THREE.Vector3());
    targetSystem.position.copy(anchor);
    targetSystem.visible = false;
    targetSystem.scale.setScalar(0.001);
    allSystems.forEach((system) => {
      if (system !== targetSystem && system !== previousSystem) {
        system.visible = false;
        system.scale.setScalar(0.001);
      }
    });
    beginTransition();
    const reveal = mode === 'family'
      ? { x: anchor.x + 0.55, y: anchor.y + 2.55, z: anchor.z + 4.85 }
      : { x: anchor.x + 0.65, y: anchor.y + 3.25, z: anchor.z + 5.15 };
    const enteringFromGalaxy = galaxyGroup.visible;
    engine.currentSystem = targetSystem;

    if (enteringFromGalaxy) {
      timeline
        .addLabel('zoom')
        .to(camera.position, { ...reveal, duration: 0.56 * motionScale }, 'zoom')
        .to(controls.target, { x: anchor.x, y: anchor.y, z: anchor.z, duration: 0.56 * motionScale }, 'zoom')
        .addLabel('galaxyOut')
        .to(galaxyMaterial.uniforms.uOpacity, { value: 0.0025, duration: 0.24 * motionScale }, 'galaxyOut')
        .to(backgroundMaterial.uniforms.uOpacity, { value: mode === 'family' ? 0.55 : 0.5, duration: 0.24 * motionScale }, 'galaxyOut')
        .addLabel('systemIn')
        .call(() => {
          galaxyGroup.visible = false;
          targetSystem.visible = true;
        }, [], 'systemIn')
        .to(targetSystem.scale, {
          x: 1,
          y: 1,
          z: 1,
          duration: 0.42 * motionScale,
          ease: 'expo.out',
          onComplete: () => finishTransition({
            minDistance: mode === 'family' ? 2.5 : 3.2,
            maxDistance: mode === 'family' ? 7.2 : 8.5,
            currentSystem: targetSystem,
          }),
        }, 'systemIn');
    } else {
      targetSystem.visible = true;
      timeline
        .addLabel('systemChange')
        .to(previousSystem.scale, {
          x: 0.001,
          y: 0.001,
          z: 0.001,
          duration: 0.28 * motionScale,
          ease: 'power2.in',
          onComplete: () => { previousSystem.visible = false; },
        }, 'systemChange')
        .to(camera.position, { ...reveal, duration: 0.56 * motionScale }, 'systemChange')
        .to(controls.target, { x: anchor.x, y: anchor.y, z: anchor.z, duration: 0.56 * motionScale }, 'systemChange')
        .to(targetSystem.scale, {
          x: 1,
          y: 1,
          z: 1,
          duration: 0.42 * motionScale,
          ease: 'expo.out',
          onComplete: () => finishTransition({
            minDistance: mode === 'family' ? 2.5 : 3.2,
            maxDistance: mode === 'family' ? 7.2 : 8.5,
            currentSystem: targetSystem,
          }),
        }, 'systemChange+=0.18');
    }

    return () => timeline.kill();
  }, [engineVersion, focusDomainId, focusFamilyId, mode]);

  useEffect(() => {
    const engine = engineRef.current;
    if (!engine) return;
    engine.nodeObjects.forEach((objects, id) => {
      objects.forEach(({ visual, glow }) => {
        const active = id === selectedId;
        visual.userData.selected = active;
        gsap.to(visual.scale, { x: active ? 1.42 : 1, y: active ? 1.42 : 1, z: active ? 1.42 : 1, duration: 0.24, ease: 'power3.out', overwrite: 'auto' });
        gsap.to(glow.material, { opacity: active ? 1 : 0.72, duration: 0.24, overwrite: 'auto' });
        const label = visual.parent?.children?.find((child) => child.isCSS2DObject)?.element;
        label?.classList.toggle('is-selected', active);
      });
    });
  }, [selectedId]);

  return <div ref={mountRef} className="graph-webgl-scene galaxy-navigation-scene" data-mode={mode} />;
};

export default GalaxyScene;
