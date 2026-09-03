import React, { useEffect, useRef } from 'react';
import * as THREE from 'three';

export const Studio3DSphere: React.FC = () => {
  const containerRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    // ─── Scene & Camera ─────────────────────────────────────────
    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(
      36,
      container.clientWidth / container.clientHeight,
      0.1,
      1000
    );
    camera.position.set(0, 0.5, 8.8);

    // ─── WebGL Renderer ─────────────────────────────────────────
    const renderer = new THREE.WebGLRenderer({
      antialias: true,
      alpha: true,
      powerPreference: 'high-performance',
    });
    renderer.setSize(container.clientWidth, container.clientHeight);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.toneMapping = THREE.ACESFilmicToneMapping;
    renderer.toneMappingExposure = 1.25;
    renderer.shadowMap.enabled = true;
    renderer.shadowMap.type = THREE.PCFSoftShadowMap;
    container.appendChild(renderer.domElement);

    // ─── Main World Group ───────────────────────────────────────
    const group = new THREE.Group();
    group.position.set(-0.15, -1.9, 0);
    scene.add(group);

    // ═════════════════════════════════════════════════════════════
    // 1. INNER GLOBE (Revealed when outer sphere breaks!)
    //    Solid white/cream core + Dense red square lat/long grid
    // ═════════════════════════════════════════════════════════════
    const INNER_RADIUS = 2.95;

    // Solid pale cream/white inner core
    const innerSolidMat = new THREE.MeshStandardMaterial({
      color: 0xFFF7F5,
      roughness: 0.5,
      metalness: 0.02,
    });
    const innerSolid = new THREE.Mesh(
      new THREE.SphereGeometry(INNER_RADIUS * 0.99, 64, 64),
      innerSolidMat
    );
    group.add(innerSolid);

    // Dense Lat/Long Square Grid Lines (Exact match to reference)
    const gridGeo = new THREE.SphereGeometry(INNER_RADIUS, 80, 50);
    const gridMat = new THREE.MeshBasicMaterial({
      color: 0xD04A40,
      wireframe: true,
      transparent: true,
      opacity: 0.5,
    });
    const innerGrid = new THREE.Mesh(gridGeo, gridMat);
    group.add(innerGrid);

    // ═════════════════════════════════════════════════════════════
    // 2. GLOSSY OBSIDIAN BALL (Single, Smaller, PURE JET BLACK)
    //    Size reduced, metalness set low so it stays deep pitch black
    // ═════════════════════════════════════════════════════════════
    const BALL_RADIUS = 0.72; // Reduced size as requested
    const obsidianMat = new THREE.MeshPhysicalMaterial({
      color: 0x000000,      // Pure pitch black
      roughness: 0.02,
      metalness: 0.05,     // Low metalness ensures it does NOT turn grey/silver!
      clearcoat: 1.0,      // Shiny glass lacquer finish
      clearcoatRoughness: 0.02,
      reflectivity: 1.0,
    });
    const ballMesh = new THREE.Mesh(
      new THREE.SphereGeometry(BALL_RADIUS, 64, 64),
      obsidianMat
    );
    ballMesh.castShadow = true;
    group.add(ballMesh);

    // Specular Highlight Circles on Ball (Softbox studio reflections)
    const hlMat = new THREE.MeshBasicMaterial({
      color: 0xFFFFFF,
      transparent: true,
      opacity: 0.98,
      depthWrite: false,
    });

    const hl1 = new THREE.Mesh(new THREE.CircleGeometry(BALL_RADIUS * 0.28, 32), hlMat);
    hl1.position.set(-BALL_RADIUS * 0.26, BALL_RADIUS * 0.46, BALL_RADIUS * 0.88);
    hl1.rotation.set(-0.12, 0.18, 0);
    ballMesh.add(hl1);

    const hl2 = new THREE.Mesh(new THREE.CircleGeometry(BALL_RADIUS * 0.13, 32), hlMat.clone());
    hl2.material.opacity = 0.9;
    hl2.position.set(-BALL_RADIUS * 0.48, BALL_RADIUS * 0.2, BALL_RADIUS * 0.85);
    hl2.rotation.set(-0.08, 0.3, 0);
    ballMesh.add(hl2);

    const hl3 = new THREE.Mesh(new THREE.CircleGeometry(BALL_RADIUS * 0.08, 32), hlMat.clone());
    hl3.material.opacity = 0.7;
    hl3.position.set(-BALL_RADIUS * 0.18, -BALL_RADIUS * 0.32, BALL_RADIUS * 0.9);
    ballMesh.add(hl3);

    // ═════════════════════════════════════════════════════════════
    // 3. FRACTURED OUTER CORAL SHELL TILES
    //    Tiles break and peel open around the ball's position!
    // ═════════════════════════════════════════════════════════════
    const OUTER_RADIUS = 3.32;
    const tilesGroup = new THREE.Group();
    group.add(tilesGroup);

    // Generate faceted tiles from an icosahedron geometry
    const baseGeo = new THREE.IcosahedronGeometry(OUTER_RADIUS, 3);
    const nonIndexedBase = baseGeo.toNonIndexed();
    const posAttr = nonIndexedBase.attributes.position;
    const faceCount = posAttr.count / 3;

    interface ShellTile {
      mesh: THREE.Mesh;
      basePos: THREE.Vector3;
      normal: THREE.Vector3;
      baseRot: THREE.Euler;
      randomTilt: THREE.Vector3;
      randomOffset: number;
    }

    const shellTiles: ShellTile[] = [];

    const tileColors = [
      0xD94F45, 0xE45D52, 0xC83B30, 0xDE564B, 0xEF6E63, 0xB83025,
    ];

    const tileMats = tileColors.map(
      (c) =>
        new THREE.MeshStandardMaterial({
          color: c,
          roughness: 0.32,
          metalness: 0.06,
          flatShading: true,
          side: THREE.DoubleSide,
        })
    );

    for (let i = 0; i < faceCount; i++) {
      const vA = new THREE.Vector3().fromBufferAttribute(posAttr, i * 3);
      const vB = new THREE.Vector3().fromBufferAttribute(posAttr, i * 3 + 1);
      const vC = new THREE.Vector3().fromBufferAttribute(posAttr, i * 3 + 2);

      const center = new THREE.Vector3()
        .add(vA)
        .add(vB)
        .add(vC)
        .divideScalar(3);

      const normal = center.clone().normalize();

      const tileGeo = new THREE.BufferGeometry();
      const localA = vA.clone().sub(center);
      const localB = vB.clone().sub(center);
      const localC = vC.clone().sub(center);

      const vertices = new Float32Array([
        localA.x, localA.y, localA.z,
        localB.x, localB.y, localB.z,
        localC.x, localC.y, localC.z,
      ]);
      tileGeo.setAttribute('position', new THREE.BufferAttribute(vertices, 3));
      tileGeo.computeVertexNormals();

      const mat = tileMats[i % tileMats.length];
      const mesh = new THREE.Mesh(tileGeo, mat);
      mesh.position.copy(center);

      tilesGroup.add(mesh);

      shellTiles.push({
        mesh,
        basePos: center.clone(),
        normal: normal.clone(),
        baseRot: mesh.rotation.clone(),
        randomTilt: new THREE.Vector3(
          (Math.random() - 0.5) * 0.8,
          (Math.random() - 0.5) * 0.8,
          (Math.random() - 0.5) * 0.8
        ),
        randomOffset: Math.random(),
      });
    }

    // ═════════════════════════════════════════════════════════════
    // 4. SUBTLE CRATER RIM SHARDS
    //    Small, refined flat shards along fracture boundary
    // ═════════════════════════════════════════════════════════════
    const debrisGroup = new THREE.Group();
    group.add(debrisGroup);

    const debrisList: {
      mesh: THREE.Mesh;
      relAngle: number;
      distOffset: number;
      lift: number;
      rotSpeed: THREE.Vector3;
    }[] = [];

    const debrisChipGeo = new THREE.BoxGeometry(0.12, 0.09, 0.02);
    const chipMat = new THREE.MeshStandardMaterial({
      color: 0xC4382D,
      roughness: 0.35,
      metalness: 0.04,
      flatShading: true,
      side: THREE.DoubleSide,
    });

    for (let i = 0; i < 20; i++) {
      const chip = new THREE.Mesh(debrisChipGeo, chipMat);
      debrisGroup.add(chip);
      debrisList.push({
        mesh: chip,
        relAngle: (i / 20) * Math.PI * 2 + (Math.random() - 0.5) * 0.3,
        distOffset: 0.85 + Math.random() * 0.45,
        lift: 0.08 + Math.random() * 0.2,
        rotSpeed: new THREE.Vector3(
          (Math.random() - 0.5) * 0.02,
          (Math.random() - 0.5) * 0.02,
          (Math.random() - 0.5) * 0.02
        ),
      });
    }

    // ═════════════════════════════════════════════════════════════
    // 5. LIGHTING SETUP
    // ═════════════════════════════════════════════════════════════
    const keyLight = new THREE.DirectionalLight(0xFFFAF5, 3.0);
    keyLight.position.set(7, 12, 9);
    keyLight.castShadow = true;
    scene.add(keyLight);

    const fillLight = new THREE.DirectionalLight(0xFFE4DC, 1.2);
    fillLight.position.set(-7, 4, 6);
    scene.add(fillLight);

    const rimLight = new THREE.DirectionalLight(0xFF7A68, 2.5);
    rimLight.position.set(-5, -4, -6);
    scene.add(rimLight);

    scene.add(new THREE.AmbientLight(0xFFF2EE, 1.5));

    const coralGlow = new THREE.PointLight(0xE5584D, 3.5, 12);
    coralGlow.position.set(0, 1.5, 4.5);
    scene.add(coralGlow);

    // ═════════════════════════════════════════════════════════════
    // 6. INTERACTIVE MOUSE RAYCASTING & MOVEMENT
    // ═════════════════════════════════════════════════════════════
    let mouseX = 0;
    let mouseY = 0;
    let hasMouseInteracted = false;

    const raycaster = new THREE.Raycaster();
    const mouse2D = new THREE.Vector2(-999, -999);
    const virtualSphereGeo = new THREE.SphereGeometry(OUTER_RADIUS, 16, 16);
    const virtualSphereMesh = new THREE.Mesh(
      virtualSphereGeo,
      new THREE.MeshBasicMaterial({ visible: false })
    );
    group.add(virtualSphereMesh);

    const currentBallPos = new THREE.Vector3(-1.4, 2.3, 2.1);
    const targetBallPos = new THREE.Vector3(-1.4, 2.3, 2.1);

    const onPointerMove = (e: PointerEvent) => {
      const rect = container.getBoundingClientRect();
      const x = ((e.clientX - rect.left) / rect.width) * 2 - 1;
      const y = -(((e.clientY - rect.top) / rect.height) * 2 - 1);

      mouse2D.set(x, y);
      mouseX = x;
      mouseY = y;
      hasMouseInteracted = true;

      raycaster.setFromCamera(mouse2D, camera);
      const intersects = raycaster.intersectObject(virtualSphereMesh);

      if (intersects.length > 0) {
        const hit = intersects[0].point;
        const localHit = group.worldToLocal(hit.clone());
        localHit.normalize().multiplyScalar(OUTER_RADIUS * 0.96);
        targetBallPos.copy(localHit);
      }
    };

    container.addEventListener('pointermove', onPointerMove);

    const onResize = () => {
      if (!container) return;
      camera.aspect = container.clientWidth / container.clientHeight;
      camera.updateProjectionMatrix();
      renderer.setSize(container.clientWidth, container.clientHeight);
    };
    window.addEventListener('resize', onResize);

    // ═════════════════════════════════════════════════════════════
    // 7. ANIMATION LOOP (Dynamic breaking wherever ball moves!)
    // ═════════════════════════════════════════════════════════════
    let animId: number;
    const clock = new THREE.Clock();

    const animate = () => {
      animId = requestAnimationFrame(animate);
      const t = clock.getElapsedTime();

      // Idle smooth orbit if user has not hovered yet
      if (!hasMouseInteracted) {
        const orbitPhi = Math.sin(t * 0.45) * 0.4 - 0.15;
        const orbitTheta = Math.PI * 0.35 + Math.cos(t * 0.38) * 0.3;

        targetBallPos.set(
          OUTER_RADIUS * Math.sin(orbitTheta) * Math.sin(orbitPhi) - 0.4,
          OUTER_RADIUS * Math.cos(orbitTheta) + 1.1,
          OUTER_RADIUS * Math.sin(orbitTheta) * Math.cos(orbitPhi) + 0.8
        ).normalize().multiplyScalar(OUTER_RADIUS * 0.96);
      }

      currentBallPos.lerp(targetBallPos, 0.055);
      ballMesh.position.copy(currentBallPos);

      // Roll ball rotation
      ballMesh.rotation.x += 0.012;
      ballMesh.rotation.y += 0.008;

      // Group idle parallax
      group.rotation.y = Math.sin(t * 0.06) * 0.06 + mouseX * 0.12;
      group.rotation.x = Math.cos(t * 0.05) * 0.04 - mouseY * 0.08;

      // ─── DYNAMIC FRACTURE LOGIC ─────────────────────────────────
      // Adjusted for the smaller ball radius
      const HOLE_RADIUS = 0.95;   // Inside this radius: shell cleanly removed to reveal grid!
      const CRATER_RADIUS = 1.65; // Between HOLE and CRATER: tiles lift, tilt, and shatter

      for (let i = 0; i < shellTiles.length; i++) {
        const tile = shellTiles[i];
        const dist = tile.basePos.distanceTo(currentBallPos);

        if (dist < HOLE_RADIUS) {
          // Inside hole: tile hidden
          tile.mesh.scale.set(0, 0, 0);
        } else if (dist < CRATER_RADIUS) {
          // Crater rim: tile lifts and tilts
          const rimProgress = (dist - HOLE_RADIUS) / (CRATER_RADIUS - HOLE_RADIUS);
          const lift = (1 - rimProgress) * 0.42;
          const scale = 0.4 + rimProgress * 0.6;

          tile.mesh.position
            .copy(tile.basePos)
            .addScaledVector(tile.normal, lift + Math.sin(t * 2 + tile.randomOffset) * 0.015);

          tile.mesh.rotation.set(
            tile.baseRot.x + tile.randomTilt.x * (1 - rimProgress) * 1.3,
            tile.baseRot.y + tile.randomTilt.y * (1 - rimProgress) * 1.3,
            tile.baseRot.z + tile.randomTilt.z * (1 - rimProgress) * 1.3
          );

          tile.mesh.scale.set(scale, scale, scale);
        } else {
          // Intact shell
          tile.mesh.position.copy(tile.basePos);
          tile.mesh.rotation.copy(tile.baseRot);
          tile.mesh.scale.set(1, 1, 1);
        }
      }

      // Debris around the crater
      const ballNorm = currentBallPos.clone().normalize();
      const up = new THREE.Vector3(0, 1, 0);
      const tangentX = new THREE.Vector3().crossVectors(ballNorm, up).normalize();
      const tangentY = new THREE.Vector3().crossVectors(ballNorm, tangentX).normalize();

      for (let i = 0; i < debrisList.length; i++) {
        const d = debrisList[i];
        const angle = d.relAngle + t * 0.18;
        const radius = d.distOffset;

        const offset = tangentX
          .clone()
          .multiplyScalar(Math.cos(angle) * radius)
          .add(tangentY.clone().multiplyScalar(Math.sin(angle) * radius))
          .add(ballNorm.clone().multiplyScalar(d.lift));

        d.mesh.position.copy(currentBallPos).add(offset);
        d.mesh.rotation.x += d.rotSpeed.x;
        d.mesh.rotation.y += d.rotSpeed.y;
        d.mesh.rotation.z += d.rotSpeed.z;
      }

      renderer.render(scene, camera);
    };

    animate();

    return () => {
      cancelAnimationFrame(animId);
      container.removeEventListener('pointermove', onPointerMove);
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
      className="w-full h-full min-h-[500px] cursor-grab active:cursor-grabbing select-none relative"
      style={{ touchAction: 'none' }}
    />
  );
};
