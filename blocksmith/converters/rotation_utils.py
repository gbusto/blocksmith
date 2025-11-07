"""
Centralized quaternion/Euler conversion utilities for v3 schema.

All format engines (GLTF, Bedrock, BBModel, Python) should use these utilities
to ensure consistent, accurate rotations across formats.

Key principles:
- Fixed 'XYZ' Euler order for consistency
- Use scipy when available for maximum accuracy
- Normalize angle ranges to [-180°, 180°] for LLM-friendly output
- Handle gimbal lock gracefully
"""

import math
from typing import List, Tuple, Optional

try:
    from scipy.spatial.transform import Rotation
    SCIPY_AVAILABLE = True
except ImportError:
    SCIPY_AVAILABLE = False

# Fixed rotation order for all conversions
EULER_ORDER = 'XYZ'

def quaternion_to_euler(quat: List[float]) -> List[float]:
    """
    Convert quaternion [w, x, y, z] to Euler angles [x, y, z] in degrees.
    
    Uses fixed XYZ order and normalizes angles to [-180°, 180°] range
    for consistent, LLM-friendly output.
    
    Args:
        quat: Quaternion as [w, x, y, z]
    
    Returns:
        Euler angles in degrees [x_roll, y_pitch, z_yaw]
    """
    if SCIPY_AVAILABLE:
        # scipy expects [x, y, z, w] format
        w, x, y, z = quat
        r = Rotation.from_quat([x, y, z, w])
        euler_rad = r.as_euler(EULER_ORDER)
        # Convert to degrees and normalize to [-180, 180] range
        euler_deg = [math.degrees(angle) for angle in euler_rad]
        return [_normalize_angle(angle) for angle in euler_deg]
    else:
        # Fallback implementation for XYZ order
        return _quaternion_to_euler_xyz_fallback(quat)

def euler_to_quaternion(euler: List[float]) -> List[float]:
    """
    Convert Euler angles [x, y, z] in degrees to quaternion [w, x, y, z].
    
    Uses fixed XYZ order for consistency.
    
    Args:
        euler: Euler angles in degrees [x_roll, y_pitch, z_yaw]
    
    Returns:
        Normalized quaternion as [w, x, y, z] with consistent sign (w >= 0)
    """
    if SCIPY_AVAILABLE:
        # Convert to radians
        euler_rad = [math.radians(angle) for angle in euler]
        r = Rotation.from_euler(EULER_ORDER, euler_rad)
        # scipy returns [x, y, z, w], we want [w, x, y, z]
        x, y, z, w = r.as_quat()
        quat = [w, x, y, z]
    else:
        # Fallback implementation for XYZ order
        quat = _euler_to_quaternion_xyz_fallback(euler)
    
    # Ensure consistent sign convention
    return _normalize_quaternion(quat)

def is_gimbal_lock(euler: List[float], tolerance: float = 0.01) -> bool:
    """
    Check if Euler angles are near gimbal lock (Y pitch ≈ ±90°).
    
    Args:
        euler: Euler angles in degrees [x, y, z]
        tolerance: Tolerance for detecting lock condition (default 0.01 degrees)
    
    Returns:
        True if near gimbal lock
    """
    _, pitch, _ = euler
    return abs(abs(pitch) - 90.0) < tolerance

def test_roundtrip_accuracy(quat: List[float]) -> Tuple[List[float], float]:
    """
    Test roundtrip accuracy: quat -> euler -> quat.
    
    Args:
        quat: Original quaternion [w, x, y, z]
    
    Returns:
        Tuple of (final_quat, angular_error_degrees)
    """
    euler = quaternion_to_euler(quat)
    final_quat = euler_to_quaternion(euler)
    
    # Calculate angular error between quaternions
    error_deg = _quaternion_angular_error(quat, final_quat)
    
    return final_quat, error_deg

def _normalize_angle(angle_deg: float) -> float:
    """Normalize angle to [-180, 180] range."""
    while angle_deg > 180:
        angle_deg -= 360
    while angle_deg <= -180:
        angle_deg += 360
    return round(angle_deg, 2)  # Round to 2 decimal places for clean output

def _quaternion_angular_error(q1: List[float], q2: List[float]) -> float:
    """Calculate angular error between two quaternions in degrees."""
    # Normalize quaternions
    q1_norm = _normalize_quaternion(q1)
    q2_norm = _normalize_quaternion(q2)
    
    # Calculate dot product (clamped to [-1, 1] for numerical stability)
    dot = sum(a * b for a, b in zip(q1_norm, q2_norm))
    dot = max(-1.0, min(1.0, abs(dot)))  # abs() because q and -q represent same rotation
    
    # Angular error = 2 * arccos(|dot|)
    return 2 * math.degrees(math.acos(dot))

def _normalize_quaternion(quat: List[float]) -> List[float]:
    """Normalize quaternion to unit length and ensure consistent sign (w >= 0)."""
    magnitude = math.sqrt(sum(x * x for x in quat))
    if magnitude == 0:
        return [1, 0, 0, 0]  # Identity quaternion
    
    # Normalize to unit length
    normalized = [x / magnitude for x in quat]
    
    # Ensure w component is non-negative for consistent representation
    # (q and -q represent the same rotation, so we choose w >= 0 convention)
    if normalized[0] < 0:
        normalized = [-x for x in normalized]
    
    return normalized

def _quaternion_to_euler_xyz_fallback(quat: List[float]) -> List[float]:
    """
    Fallback quaternion to Euler conversion for XYZ order.
    Less accurate than scipy but available without dependencies.
    """
    w, x, y, z = _normalize_quaternion(quat)
    
    # XYZ order conversion
    # Roll (X-axis rotation)
    sinr_cosp = 2 * (w * x + y * z)
    cosr_cosp = 1 - 2 * (x * x + y * y)
    roll = math.atan2(sinr_cosp, cosr_cosp)
    
    # Pitch (Y-axis rotation)
    sinp = 2 * (w * y - z * x)
    if abs(sinp) >= 1:
        pitch = math.copysign(math.pi / 2, sinp)  # Use 90 degrees if out of range
    else:
        pitch = math.asin(sinp)
    
    # Yaw (Z-axis rotation)
    siny_cosp = 2 * (w * z + x * y)
    cosy_cosp = 1 - 2 * (y * y + z * z)
    yaw = math.atan2(siny_cosp, cosy_cosp)
    
    # Convert to degrees and normalize
    euler_deg = [math.degrees(roll), math.degrees(pitch), math.degrees(yaw)]
    return [_normalize_angle(angle) for angle in euler_deg]

def _euler_to_quaternion_xyz_fallback(euler: List[float]) -> List[float]:
    """
    Fallback Euler to quaternion conversion for XYZ order.
    Less accurate than scipy but available without dependencies.
    """
    # Convert to radians
    roll, pitch, yaw = [math.radians(angle) for angle in euler]
    
    # XYZ order quaternion composition
    cr = math.cos(roll * 0.5)
    sr = math.sin(roll * 0.5)
    cp = math.cos(pitch * 0.5)
    sp = math.sin(pitch * 0.5)
    cy = math.cos(yaw * 0.5)
    sy = math.sin(yaw * 0.5)
    
    # XYZ order multiplication
    w = cr * cp * cy - sr * sp * sy
    x = sr * cp * cy + cr * sp * sy
    y = cr * sp * cy - sr * cp * sy
    z = cr * cp * sy + sr * sp * cy
    
    return _normalize_quaternion([w, x, y, z])