import numpy as np

GRAVITY = 9.80665  # Standard gravity in m/s^2

def calibrate_accel_6point(readings):
    """
    Calibrate accelerometer using PX4 6-point method.
    
    Args:
        readings: List of 6 readings, each a 3-element iterable (x, y, z),
                  corresponding to the 6 orientations:
                  +X, -X, +Y, -Y, +Z, -Z
        
    Returns:
        offsets: np.array([ox, oy, oz])
        scales:  np.array([sx, sy, sz])
    """
    if len(readings) != 6:
        raise ValueError("Exactly 6 measurements required.")
    
    # Expected gravity vector directions for each orientation
    expected = np.array([
        [+GRAVITY,     0.0,     0.0],  # +X
        [-GRAVITY,     0.0,     0.0],  # -X
        [    0.0, +GRAVITY,     0.0],  # +Y
        [    0.0, -GRAVITY,     0.0],  # -Y
        [    0.0,     0.0, +GRAVITY],  # +Z
        [    0.0,     0.0, -GRAVITY],  # -Z
    ])
    
    # Build design matrix A and observation vector b
    A = []
    b = []
    for meas, exp in zip(readings, expected):
        for i in range(3):
            row = [0]*6
            row[i] = 1        # offset
            row[i+3] = meas[i]  # scale * reading
            A.append(row)
            b.append(exp[i])
    
    A = np.array(A)
    b = np.array(b)

    # Solve least squares: A x = b
    x, residuals, rank, s = np.linalg.lstsq(A, b, rcond=None)
    
    offsets = x[:3]
    scales = x[3:]
    
    return offsets, scales

# Simulated noisy readings at 6 orientations
readings = [
    [ 9.80,  0.05, -0.02],   # +X
    [-9.78,  0.02,  0.01],   # -X
    [-0.03,  9.81,  0.04],   # +Y
    [ 0.02, -9.79, -0.01],   # -Y
    [ 0.01,  0.02,  9.82],   # +Z
    [ 0.00, -0.01, -9.80],   # -Z
]

offsets, scales = calibrate_accel_6point(readings)

print("Offsets:", offsets)
print("Scales:", scales)
