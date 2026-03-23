import { useRef, useMemo } from 'react'
import { Canvas, useFrame } from '@react-three/fiber'
import { OrbitControls, Stars, Text } from '@react-three/drei'
import * as THREE from 'three'

const PLANETS = [
    { name: 'Mercury', distance: 10, size: 0.8,  color: '#94a3b8', speed: 0.8,  offset: 0 },
    { name: 'Venus',   distance: 15, size: 1.2,  color: '#fb923c', speed: 0.6,  offset: 1.2 },
    { name: 'Earth',   distance: 20, size: 1.3,  color: '#3b82f6', speed: 0.4,  offset: 2.5 },
    { name: 'Mars',    distance: 26, size: 1.0,  color: '#ef4444', speed: 0.3,  offset: 3.8 },
    { name: 'Jupiter', distance: 38, size: 3.5,  color: '#d97706', speed: 0.15, offset: 0.5 },
    { name: 'Saturn',  distance: 50, size: 3.0,  color: '#eab308', speed: 0.1,  offset: 1.8 },
]

// ------------------------------------------------------------------
// Orbit ring (static)
// ------------------------------------------------------------------
const OrbitRing = ({ distance }) => (
    <mesh rotation={[-Math.PI / 2, 0, 0]}>
        <ringGeometry args={[distance - 0.08, distance + 0.08, 128]} />
        <meshBasicMaterial color="#1e2d4a" side={THREE.DoubleSide} transparent opacity={0.35} />
    </mesh>
)

// ------------------------------------------------------------------
// Interactive planet
// ------------------------------------------------------------------
const Planet = ({ name, distance, size, color, speed, offset, onClick, learned }) => {
    const meshRef  = useRef()
    const groupRef = useRef()

    useFrame(({ clock }) => {
        const t = clock.getElapsedTime() * speed + offset
        groupRef.current.position.set(Math.cos(t) * distance, 0, Math.sin(t) * distance)
    })

    // Glow emissive strength: higher when learned
    const emissiveIntensity = learned ? 1.4 : 0.5

    return (
        <group ref={groupRef}>
            {/* Clickable sphere */}
            <mesh
                ref={meshRef}
                onClick={(e) => { e.stopPropagation(); onClick(name) }}
                onPointerOver={() => { document.body.style.cursor = 'pointer' }}
                onPointerOut={() =>  { document.body.style.cursor = 'default'  }}
            >
                <sphereGeometry args={[size, 32, 32]} />
                <meshStandardMaterial
                    color={color}
                    emissive={learned ? '#06b6d4' : color}
                    emissiveIntensity={emissiveIntensity}
                    roughness={0.3}
                    metalness={0.7}
                />
            </mesh>

            {/* Label */}
            <Text
                position={[0, size + 1.8, 0]}
                fontSize={0.7}
                color={learned ? '#67e8f9' : 'white'}
                anchorX="center"
                anchorY="middle"
                outlineWidth={0.05}
                outlineColor="#000"
            >
                {name}
            </Text>

            {/* Learned ring pulse */}
            {learned && (
                <mesh rotation={[-Math.PI / 2, 0, 0]}>
                    <ringGeometry args={[size + 0.4, size + 0.6, 64]} />
                    <meshBasicMaterial color="#06b6d4" transparent opacity={0.4} side={THREE.DoubleSide} />
                </mesh>
            )}
        </group>
    )
}

// ------------------------------------------------------------------
// Sun
// ------------------------------------------------------------------
const Sun = () => (
    <mesh>
        <sphereGeometry args={[5, 64, 64]} />
        <meshStandardMaterial color="#fbbf24" emissive="#f59e0b" emissiveIntensity={2.5} />
        <pointLight intensity={12} distance={120} color="#fbbf24" />
    </mesh>
)

// ------------------------------------------------------------------
// Main scene
// ------------------------------------------------------------------
const SolarSystem = ({ onPlanetClick = () => {}, learnedTopics = [] }) => {
    const learnedSet = useMemo(() => new Set(learnedTopics.map(t => t.toLowerCase())), [learnedTopics])

    return (
        <div className="w-full h-full">
            <Canvas camera={{ position: [0, 42, 65], fov: 45 }}>
                <color attach="background" args={['#020617']} />
                <ambientLight intensity={0.25} />
                <Stars radius={300} depth={60} count={20000} factor={7} saturation={0} fade speed={0.5} />

                <Sun />

                {PLANETS.map(p => (
                    <group key={p.name}>
                        <OrbitRing distance={p.distance} />
                        <Planet
                            {...p}
                            onClick={onPlanetClick}
                            learned={learnedSet.has(p.name.toLowerCase())}
                        />
                    </group>
                ))}

                <OrbitControls makeDefault enableDamping dampingFactor={0.06} />
            </Canvas>
        </div>
    )
}

export default SolarSystem
