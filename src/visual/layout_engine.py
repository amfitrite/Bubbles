import math
import numpy as np
from typing import List, Dict
from dataclasses import dataclass
from src.algo.models import AlgoBubble
from src.visual.camera import Camera

@dataclass
class VisualBubble:
    """
    Visual Presentation Node.
    Couples adjusted ergonomic screen coordinates (with guaranteed pixel gaps)
    with the 100% uncorrupted mathematical AlgoBubble.
    """
    visual_x: float     # Screen X with collision/gap padding applied
    visual_y: float     # Screen Y with collision/gap padding applied
    radius: float       # Visual radius
    raw_sx: float       # Unaltered camera projected screen X
    raw_sy: float       # Unaltered camera projected screen Y
    algo: AlgoBubble    # Pure uncorrupted mathematical truth

class VisualLayoutEngine:
    """
    Decoupled Visual Layout & Spacing Engine.
    Guarantees visual breathing room (anti-clumping) between bubbles without modifying
    or distorting any underlying algorithmic price/volume/delta calculations.
    """
    def __init__(self, min_gap_px: float = 5.0, size_scale: float = 1.0):
        self.min_gap_px = min_gap_px
        self.size_scale = size_scale
        self.min_radius = 3.0
        self.max_radius = 26.0

    def compute_radius(self, volume: float, p95_volume: float) -> float:
        r_min = max(2.5, self.min_radius * self.size_scale)
        r_max = self.max_radius * self.size_scale

        if volume <= 1.0:
            return r_min

        eff_p95 = max(5.0, p95_volume)
        norm = max(0.0, min(2.0, (volume - 1.0) / (eff_p95 - 1.0)))
        rad = r_min + (r_max - r_min) * math.sqrt(norm)
        return max(r_min, min(r_max, rad))

    def process_layout(self, algo_bubbles: List[AlgoBubble], camera: Camera,
                       min_volume_filter: float = 0.0) -> List[VisualBubble]:
        """
        Transforms AlgoBubbles into visually comfortable, non-overlapping VisualBubbles.
        """
        if not algo_bubbles:
            return []

        # Filter min volume if requested
        valid_bubbles = [b for b in algo_bubbles if b.volume >= min_volume_filter] if min_volume_filter > 0 else algo_bubbles
        if not valid_bubbles:
            return []

        # Calculate robust P95 volume for proportional bubble sizing
        vols = np.array([b.volume for b in valid_bubbles])
        p95_v = float(np.percentile(vols, 95)) if len(vols) >= 5 else float(np.max(vols))

        w = camera.width
        h = camera.height
        visual_nodes: List[VisualBubble] = []

        # 1. Project raw screen coordinates and assign radius
        for b in valid_bubbles:
            raw_sx = camera.time_to_screen_x(b.ts)
            raw_sy = camera.price_to_screen_y(b.price)

            # Cull bubbles far outside viewport boundaries
            if raw_sx < -80 or raw_sx > w + 80 or raw_sy < -80 or raw_sy > h + 80:
                continue

            radius = self.compute_radius(b.volume, p95_v)
            visual_nodes.append(VisualBubble(
                visual_x=raw_sx,
                visual_y=raw_sy,
                radius=radius,
                raw_sx=raw_sx,
                raw_sy=raw_sy,
                algo=b
            ))

        if not visual_nodes:
            return []

        # 2. Pixel Gap Enforcer: Resolve visual clumping along horizontal timeline
        # Sort chronologically by raw screen X
        visual_nodes.sort(key=lambda node: (node.raw_sx, node.raw_sy))

        gap = self.min_gap_px
        if gap > 0 and len(visual_nodes) > 1:
            # Forward pass: ensure each bubble maintains at least `min_gap_px` clearance
            # from the preceding bubble if they occupy similar price levels
            for i in range(1, len(visual_nodes)):
                prev = visual_nodes[i - 1]
                curr = visual_nodes[i]

                # Check vertical proximity
                dy = abs(curr.visual_y - prev.visual_y)
                combined_r = prev.radius + curr.radius + gap

                # If vertically overlapping or close, enforce horizontal separation
                if dy < combined_r:
                    min_dx = math.sqrt(max(1.0, (combined_r * combined_r) - (dy * dy)))
                    required_x = prev.visual_x + min_dx
                    if curr.visual_x < required_x:
                        # Gently offset visual_x while keeping original raw_sx in algo untouched!
                        curr.visual_x = required_x

        # 3. Sort so larger bubbles are drawn behind smaller ones for crisp visibility
        visual_nodes.sort(key=lambda node: node.radius, reverse=True)
        return visual_nodes
