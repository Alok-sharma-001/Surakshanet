import React, { useEffect, useRef } from 'react';
import * as THREE from 'three';

export const StudioRightTotem3D: React.FC = () => {
  const containerRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    // ─── Scene & Camera ─────────────────────────────────────────
    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(
      40,
      container.clientWidth / container.clientHeight,
      0.1,
      100
    );
    camera.position.set(0, 0, 5.2);

    // ─── WebGL Renderer ─────────────────────────────────────────
    const renderer = new THREE.WebGLRenderer({
      antialias: true,
      alpha: true,
      powerPreference: 'high-performance',
    });
    renderer.setSize(container.clientWidth, container.clientHeight);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.toneMapping = THREE.ACESFilmicToneMapping;
    renderer.toneMappingExposure = 1.3;
    container.appendChild(renderer.domElement);

    // ─── Master Totem Group ─────────────────────────────────────
    const masterGroup = new THREE.Group();
    scene.add(masterGroup);

    // ─── Materials ──────────────────────────────────────────────
    // Pure pitch black obsidian with glossy glass lacquer
    const obsidianMat = new THREE.MeshPhysicalMaterial({
      color: 0x000000,
      roughness: 0.02,
      metalness: 0.04,
      reflectivity: 1.0,
      clearcoat: 1.0,
      clearcoatRoughness: 0.02,
    });

    // Coral / Pink crystalline ring material (matching media_1788378891285.png)
    const coralCrystalMat = new THREE.MeshStandardMaterial({
      color: 0xF28E84,
      roughness: 0.25,
      metalness: 0.1,
      flatShading: true,
      side: THREE.DoubleSide,
      transparent: true,
      opacity: 0.95,
    });

    // White specular highlight circles
    const hlMat = new THREE.MeshBasicMaterial({
      color: 0xFFFFFF,
      transparent: true,
      opacity: 0.98,
      depthWrite: false,
    });

    const addHighlights = (sphere: THREE.Mesh, r: number) => {
      const h1 = new THREE.Mesh(new THREE.CircleGeometry(r * 0.25, 24), hlMat);
      h1.position.set(-r * 0.28, r * 0.44, r * 0.88);
      h1.rotation.set(-0.12, 0.18, 0);
      sphere.add(h1);

      const h2 = new THREE.Mesh(new THREE.CircleGeometry(r * 0.12, 24), hlMat.clone());
      h2.material.opacity = 0.85;
      h2.position.set(-r * 0.5, r * 0.18, r * 0.85);
      sphere.add(h2);

      const h3 = new THREE.Mesh(new THREE.CircleGeometry(r * 0.08, 24), hlMat.clone());
      h3.material.opacity = 0.6;
      h3.position.set(-r * 0.18, -r * 0.38, r * 0.9);
      sphere.add(h3);
    };

    // ═════════════════════════════════════════════════════════════
    // 1. THREE VERTICALLY STACKED PURE BLACK BALLS
    //    (Exact vertical alignment matching media_1788378891285.png)
    // ═════════════════════════════════════════════════════════════
    const SPHERE_R = 0.65;
    const SPACING = 1.05; // Tight overlap matching reference

    // Top Ball
    const topSphere = new THREE.Mesh(
      new THREE.SphereGeometry(SPHERE_R, 48, 48),
      obsidianMat
    );
    topSphere.position.set(0, SPACING, 0);
    addHighlights(topSphere, SPHERE_R);
    masterGroup.add(topSphere);

    // Center Ball (encircled by the rotating coral ring)
    const midSphere = new THREE.Mesh(
      new THREE.SphereGeometry(SPHERE_R * 1.08, 48, 48),
      obsidianMat
    );
    midSphere.position.set(0, 0, 0.02);
    addHighlights(midSphere, SPHERE_R * 1.08);
    masterGroup.add(midSphere);

    // Bottom Ball
    const btmSphere = new THREE.Mesh(
      new THREE.SphereGeometry(SPHERE_R, 48, 48),
      obsidianMat
    );
    btmSphere.position.set(0, -SPACING, 0);
    addHighlights(btmSphere, SPHERE_R);
    masterGroup.add(btmSphere);

    // ═════════════════════════════════════════════════════════════
    // 2. CORAL CRYSTAL RING ENCIRCLING THE CENTER BALL
    //    Tilted forward and rotating sideways around the vertical balls
    // ═════════════════════════════════════════════════════════════
    // Group tilted forward towards the camera so user sees 3D depth of the ring
    const ringPivot = new THREE.Group();
    ringPivot.position.set(0, 0, 0);
    ringPivot.rotation.x = 0.55; // Tilted towards the screen!
    ringPivot.rotation.z = -0.15; // Elegant slight slant matching screenshot
    masterGroup.add(ringPivot);

    // The spinning ring assembly
    const spinningRing = new THREE.Group();
    ringPivot.add(spinningRing);

    // Faceted ring body
    const RING_INNER_R = 0.88;
    const RING_TUBE_R = 0.22;
    const ringGeo = new THREE.TorusGeometry(RING_INNER_R, RING_TUBE_R, 14, 32);
    const ringMesh = new THREE.Mesh(ringGeo, coralCrystalMat);
    // Orient torus flat in X-Y plane of ringPivot (so when ringPivot is tilted, it wraps around center ball)
    spinningRing.add(ringMesh);

    // Outer crystal spikes/facets around perimeter (matching jagged crystal ring)
    const teethCount = 18;
    for (let i = 0; i < teethCount; i++) {
      const angle = (i / teethCount) * Math.PI * 2;
      const toothGeo = new THREE.ConeGeometry(0.12, 0.32, 5);
      const tooth = new THREE.Mesh(toothGeo, coralCrystalMat);
      tooth.position.set(
        Math.cos(angle) * (RING_INNER_R + RING_TUBE_R * 0.9),
        Math.sin(angle) * (RING_INNER_R + RING_TUBE_R * 0.9),
        0
      );
      tooth.rotation.z = angle - Math.PI * 0.5;
      spinningRing.add(tooth);
    }

    // ═════════════════════════════════════════════════════════════
    // 3. LIGHTING SETUP
    // ═════════════════════════════════════════════════════════════
    const keyLight = new THREE.DirectionalLight(0xFFFFFF, 3.2);
    keyLight.position.set(5, 8, 6);
    scene.add(keyLight);

    const fillLight = new THREE.DirectionalLight(0xFFE8E2, 1.4);
    fillLight.position.set(-5, -2, 4);
    scene.add(fillLight);

    const coralGlow = new THREE.PointLight(0xE5584D, 3.2, 8);
    coralGlow.position.set(0, 0, 2);
    scene.add(coralGlow);

    scene.add(new THREE.AmbientLight(0xFFF2EE, 1.5));

    // ═════════════════════════════════════════════════════════════
    // 4. ANIMATION LOOP
    //    Continuous sideways rotation of the ring around the vertical balls!
    // ═════════════════════════════════════════════════════════════
    let animId: number;
    const clock = new THREE.Clock();
    let isHovered = false;

    const onMouseEnter = () => { isHovered = true; };
    const onMouseLeave = () => { isHovered = false; };

    container.addEventListener('mouseenter', onMouseEnter);
    container.addEventListener('mouseleave', onMouseLeave);

    const animate = () => {
      animId = requestAnimationFrame(animate);
      const t = clock.getElapsedTime();

      // CONTINUOUS SIDEWAYS ROTATION of the ring around the vertical balls!
      // The ring spins smoothly around its center axis
      const speed = isHovered ? 0.04 : 0.024;
      spinningRing.rotation.z += speed;

      // Gentle organic breathing of the vertical column
      masterGroup.position.y = Math.sin(t * 1.4) * 0.04;
      masterGroup.rotation.y = Math.sin(t * 0.8) * 0.06;

      renderer.render(scene, camera);
    };

    animate();

    const onResize = () => {
      if (!container) return;
      camera.aspect = container.clientWidth / container.clientHeight;
      camera.updateProjectionMatrix();
      renderer.setSize(container.clientWidth, container.clientHeight);
    };
    window.addEventListener('resize', onResize);

    return () => {
      cancelAnimationFrame(animId);
      container.removeEventListener('mouseenter', onMouseEnter);
      container.removeEventListener('mouseleave', onMouseLeave);
      window.removeEventListener('resize', onResize);
      if (renderer.domElement && container.contains(renderer.domElement)) {
        container.removeChild(renderer.domElement);
      }
      renderer.dispose();
    };
  }, []);

  return (
    <div
      ref={containerRef}
      className="w-full h-[250px] flex items-center justify-center select-none cursor-pointer"
      title="3D Rotating Ring Totem"
    />
  );
};
