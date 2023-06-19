"""
Math operations for common calculations required in Maya.

----------------------------------------------------------------

Vectors
-------

    Describe a magnitude and direction within some coordinate space.
    They have no inherent position.

Points
-------

    Describe a position within some coordinate space.
    The position is relative to a fixed origin.
    They can be described relative to each other using vectors.

    A simple analogy is time.
    Values such as ``3:00`` and ``5:00`` can be considered coordinates.
    Durations such as ``+2 hours`` can be considered vectors between time coordinates.

----------------------------------------------------------------

Cartesian Coordinates
---------------------

    Represent coordinates in n-dimensional Euclidean space using n numbers.
    For example a 3-dimensional point is defined using ``[x,y,z]`` coordinates.
    It is impossible to express a point at infinity whilst maintaining directionality.

Homogenous Coordinates
----------------------

    Graphics softwares such as Maya require a uniform way to represent points at infinity (ie. direction vectors) as well as finite Euclidean points.
    It is possible to do so using a projective space which is an extension of Euclidean space.
    Points in projective space can be represented using homogeneous coordinates.
    These coordinates allow multiple transforms such as translation, rotation, scaling and projection to be efficiently encoded within a single matrix.

    - They represent n-dimensional coordinates with n+1 numbers.
    - For example a 3-dimensional point is defined using ``[x,y,z,w]`` coordinates.
    - This coordinate can be converted to a Cartesian form using ``[x/w, y/w, z/w]``.
    - A point at infinity (ie. direction vector) is expressed using ``w=0``.
    - They are scale invariant meaning the following points are equal: ``[x,y,z,w]``, ``[A*x,A*y,A*z,A*w]``.

----------------------------------------------------------------

Matrices
--------

    Matrices can be used to encode multiple transformations within a single entity.
    Maya uses 4x4 matrices to represent transformations within 3-dimensional space.

    - Translations are encoded within the fourth row using ``w=1``.
    - Rotations are encoded within the first three rows using an orthonormal basis of direction vectors, each with ``w=0``.
    - Scaling is encoded down the diagonal from top-left to bottom-right.

----------------------------------------------------------------

Maya
----

    The Maya API makes a distinction between vectors and points via its :class:`OpenMaya.MVector` and :class:`OpenMaya.MPoint` classes.

    - An :class:`OpenMaya.MVector` is a displacement in 3-dimensional Euclidean space.
    - An :class:`OpenMaya.MPoint` is a point in the 3-dimensional projective space represented by homogeneous coordinates.
    - Subtracting one :class:`OpenMaya.MPoint` from another will return an :class:`OpenMaya.MVector` representing the displacement between points.
    - Multiplying an :class:`OpenMaya.MPoint` ``[x,y,z,0]`` by a matrix will return a new :class:`OpenMaya.MPoint` relative to the rotation and scale encoded by the matrix.
      The result is a transformed direction vector. The ``[x,y,z]`` coordinates may require normalization if scaling was present.
    - Multiplying an :class:`OpenMaya.MPoint` ``[x,y,z,1]`` by a matrix will return a new :class:`OpenMaya.MPoint` relative to the translation, rotation and scale encoded by the matrix.

----------------------------------------------------------------

Note:
    1. The homogeneous coordinate ``[0,0,0,0]`` is undefined in projective space. There is no line to project.

Note:
    2. Maya does not enforce strict conventions between vectors and points.
       For example an :class:`OpenMaya.MVector` will be treated as a Cartesian coordinate when used to instantiate an :class:`OpenMaya.MPoint`.

Note:
    3. As an optimisation, the following interface does not account for shear transforms encoded within transformation matrices.
       Alternative implementations which handle shearing can be found in the source code of this module.

.. _note_4:

Note:
    4. Certain information is lost within the encoding of a transformation matrix.
       The following assumptions are applied by this interface and the `OpenMaya`_ API when attempting to extract rotation and scaling data from a transformation matrix.

       - Negative scaling in any single axis will be extracted as negative scaling in the z-axis.
       - Negative scaling in any two axes will be extracted as a rotation around the third axis.

Warning:
    1. :meth:`OpenMaya.MPoint.cartesianize` fails for infinite points on the projected cartesian planes.
       For example the point ``[0,1,0,0]`` represents a point at infinity in the y-basis direction.
       Maya will 'cartesianize' this point as ``[nan,inf,nan,1]`` instead of the expected result ``[inf,inf,inf,1]``.
       Operations such as :meth:`OpenMaya.MPoint.distanceTo` which rely on :meth:`OpenMaya.MPoint.cartesianize` will also fail.
       The following interface does not handle this edge case.

Warning:
    2. Certain `OpenMaya`_ classes define special instances via the class attributes listed below.
       These attributes provide a reference to a single instantiation. This behaviour is dangerous since the instance is mutable.
       Changes made to these instances will affect all current and future references to the attribute and should therefore be avoided.

       - :attr:`OpenMaya.MVector.kOneVector`, :attr:`OpenMaya.MVector.kXaxisVector`, :attr:`OpenMaya.MVector.kXnegAxisVector`,
         :attr:`OpenMaya.MVector.kYaxisVector`, :attr:`OpenMaya.MVector.kYnegAxisVector`, :attr:`OpenMaya.MVector.kZaxisVector`,
         :attr:`OpenMaya.MVector.kZnegAxisVector`, :attr:`OpenMaya.MVector.kZeroVector`.
       - :attr:`OpenMaya.MPoint.kOrigin`.
       - :attr:`OpenMaya.MMatrix.kIdentity`.
       - :attr:`OpenMaya.MQuaternion.kIdentity`.

----------------------------------------------------------------
"""
import math
import sys

from maya.api import OpenMaya as om2


# --------------------------------------------------------------
# --- Exceptions ---
# --------------------------------------------------------------

class InvalidVectorError(Exception):
    """Exception to raise when:

    - Attempting to operate on or return a vector composed of ``float('nan')`` values.
    """


class InvalidPointError(Exception):
    """Exception to raise when:

    - Attempting to operate on or return the indeterminate homogeneous coordinate ``[0,0,0,0]``.
    - Attempting to operate on or return a homogeneous coordinate composed of ``float('nan')`` values.
    """


# --------------------------------------------------------------
# --- Validation ---
# --------------------------------------------------------------

def isValidVector(vector):
    """Check if a vector is numerically valid.

    Args:
        vector (iterable [numeric]): Vector in 3-dimensional Euclidean space represented by Cartesian coordinates ``[x,y,z]``.

    Returns:
        :class:`bool`: :data:`False` if any of the ``vector`` coordinates evaluate to ``float('nan')``, otherwise :data:`True`.
    """
    return not any([math.isnan(c) for c in vector])


def isInfiniteVector(vector):
    """Check if a vector has infinite magnitude.

    Args:
        vector (iterable [numeric]): Vector in 3-dimensional Euclidean space represented by Cartesian coordinates ``[x,y,z]``.

    Returns:
        :class:`bool`: :data:`True` if any of the ``vector`` coordinates evaluate to ``float('inf')``, otherwise :data:`False`.
    """
    return any([math.isinf(c) for c in vector])


def isValidPoint(point):
    """Check if a point is numerically valid.

    Args:
        point (iterable [numeric]): Position in 3-dimensional projective space represented by homogeneous coordinates ``[x,y,z,w]``.

    Returns:
        :class:`bool`: :data:`False` if any of the ``point`` coordinates evaluate to ``float('nan')`` or ``point`` is equal to ``[0,0,0,0]``, otherwise :data:`True`.
    """
    return not any([math.isnan(c) for c in point]) and any(point)


def isInfinitePoint(point):
    """Check if a point resides at infinity.

    Args:
        point (iterable [numeric]): Position in 3-dimensional projective space represented by homogeneous coordinates ``[x,y,z,w]``.

    Returns:
        :class:`bool`: :data:`True` if any of the ``point`` coordinates evaluate to ``float('inf')`` or the coordinate ``w=0``, otherwise :data:`False`.
    """
    return any([math.isinf(c) for c in point]) or point[3] == 0


def isValidVectorOrPoint(coordinates):
    """Check if a vector or point is numerically valid.

    Composition of :func:`isValidVector` and :func:`isValidPoint`, used for generic input types.

    Args:
        coordinates (iterable [numeric]): Vector in 3-dimensional Euclidean space represented by Cartesian coordinates ``[x,y,z]`` or a position in 3-dimensional projective space represented by homogeneous coordinates ``[x,y,z,w]``.

    Returns:
        :class:`bool`: :data:`False` if any of the ``coordinates`` evaluate to ``float('nan')`` or the set of ``coordinates`` is equal to ``[0,0,0,0]``, otherwise :data:`True`.
    """
    if len(coordinates) == 3:
        return isValidVector(coordinates)
    else:
        return isValidPoint(coordinates)


def isInfiniteVectorOrPoint(coordinates):
    """Check if a vector has infinite magnitude or a point is at infinity.

    Composition of :func:`isInfiniteVector` and :func:`isInfinitePoint`, used for generic input types.

    Args:
        coordinates (iterable [numeric]): Vector in 3-dimensional Euclidean space represented by Cartesian coordinates ``[x,y,z]`` or a position in 3-dimensional projective space represented by homogeneous coordinates ``[x,y,z,w]``.

    Returns:
        :class:`bool`: :data:`True` if any of the ``coordinates`` evaluate to ``float('inf')`` or the coordinate ``w=0`` if ``coordinates`` are homogeneous, otherwise :data:`False`.
    """
    if len(coordinates) == 3:
        return isInfiniteVector(coordinates)
    else:
        return isInfinitePoint(coordinates)


def isValid(value):
    """Check if a value is valid.

    Args:
        value (numeric): Numeric value.

    Returns:
        :class:`bool`: :data:`False` if ``value`` evaluates to ``float('nan')``, otherwise :data:`True`.
    """
    return not math.isnan(value)


def areClose(a, b, rTolerance=sys.float_info.epsilon, aTolerance=0.0):
    """Check if two values are approximately equal as determined by the given absolute and relative tolerances.

    Args:
        a (numeric): First value.
        b (numeric): Second value.
        rTolerance (numeric, optional): Relative tolerance, scaled to account for very large inputs.
            The scaling factor is given by ``max(max(a, b), 1)``. Defaults to the machine ``epsilon`` on :data:`sys.float_info`.
        aTolerance (numeric, optional): Absolute tolerance. Defaults to ``0.0``.

    Raises:
        :exc:`~exceptions.ValueError`: If ``rTolerance`` or ``aTolerance`` are negative.

    Returns:
        :class:`bool`: :data:`True` if ``abs(a - b)`` is less than the maximum tolerance, otherwise :data:`False`.
        The maximum tolerance is either the ``aTolerance`` or the scaled ``rTolerance``.

    Example:
        .. code-block:: python

            # Checks if `abs(a - b)` is less than an absolute tolerance
            # Returns `False` because `abs(a - b) > aTolerance`
            areClose(10.0, 10.1, rTolerance=0.0, aTolerance=0.01)

            # Checks if `abs(a - b)` is less than a relative tolerance.
            # Returns `True` because `abs(a - b) < (rTolerance * max(a, b))`
            areClose(10.0, 10.1, rTolerance=0.01, aTolerance=0.0)
    """
    if rTolerance < 0 or aTolerance < 0:
        raise ValueError("Tolerances must be non-negative")

    return abs(a - b) < max(rTolerance * max(1.0, max(abs(a), abs(b))), aTolerance)


def areCloseCoordinates(a, b):
    """Check if two coordinates are approximately equal as determined by the default Maya tolerance :attr:`OpenMaya.MVector.kTolerance`.

    The Maya tolerance is scaled to account for very large inputs.
    The scaling factor is given by ``max(max(a, b), 1)``.

    Args:
        a (numeric): First coordinate.
        b (numeric): Second coordinate.

    Returns:
        :class:`bool`: :data:`True` if ``abs(a - b)`` is less than the scaled Maya tolerance, otherwise :data:`False`.

    Example:
        .. code-block:: python

            # Checks if `abs(a - b)` is less than the scaled Maya tolerance.
            # Returns `True` because `abs(a - b) < OpenMaya.MVector.kTolerance * max(a, b)`
            areCloseCoordinates(10.0, 10.0000000001)
    """
    return abs(a - b) < om2.MVector.kTolerance * max(1.0, max(abs(a), abs(b)))


def areCloseVectors(a, b):
    """Check if two vectors are approximately equal as determined by the default Maya tolerance :attr:`OpenMaya.MVector.kTolerance`.

    The Maya tolerance is scaled to account for very large inputs.
    The scaling factor is given by ``max(max(a[i], b[i]), 1)`` for each coordinate ``i``.

    Args:
        a (iterable [numeric]): First vector in 3-dimensional Euclidean space represented by Cartesian coordinates ``[x,y,z]``.
        b (iterable [numeric]): Second vector in 3-dimensional Euclidean space represented by Cartesian coordinates ``[x,y,z]``.

    Returns:
        :class:`bool`: :data:`True` if ``abs(a[i] - b[i])`` is less than the scaled Maya tolerance for each coordinate ``i``, otherwise :data:`False`.

    Example:
        .. code-block:: python

            # Checks if `abs(a[i] - b[i])` is less than the scaled Maya tolerance for each coordinate `i`
            # Returns `True` because `abs(a[i] - b[i]) < OpenMaya.MVector.kTolerance * max(a[i], b[i])` for each coordinate `i`
            areCloseVectors([10.0, 10000.0, 10000000.0], [10.0000000001, 10000.0000001, 10000000.0001])
    """
    return (abs(a[0] - b[0]) < om2.MVector.kTolerance * max(1.0, max(abs(a[0]), abs(b[0])))
            and abs(a[1] - b[1]) < om2.MVector.kTolerance * max(1.0, max(abs(a[1]), abs(b[1])))
            and abs(a[2] - b[2]) < om2.MVector.kTolerance * max(1.0, max(abs(a[2]), abs(b[2])))
            )


def areClosePoints(a, b):
    """Check if two points are approximately equal as determined by the default Maya tolerance :attr:`OpenMaya.MVector.kTolerance`.

    The Maya tolerance is scaled to account for very large inputs.
    The scaling factor is given by ``max(max(a[i], b[i]), 1)`` for each coordinate ``i``.

    Args:
        a (iterable [numeric]): First position in 3-dimensional projective space represented by homogeneous coordinates ``[x,y,z,w]``.
        b (iterable [numeric]): Second position in 3-dimensional projective space represented by homogeneous coordinates ``[x,y,z,w]``.

    Returns:
        :class:`bool`: :data:`True` if ``abs(a[i] - b[i])`` is less than the scaled Maya tolerance for each coordinate ``i``, otherwise :data:`False`.

    Example:
        .. code-block:: python

            # Checks if `abs(a[i] - b[i])` is less than the scaled Maya tolerance for each coordinate `i`
            # Returns `True` because `abs(a[i] - b[i]) < OpenMaya.MVector.kTolerance * max(a[i], b[i])` for each coordinate `i`
            areClosePoints([10.0, 10000.0, 10000000.0, 1.0], [10.0000000001, 10000.0000001, 10000000.0001, 1.0])
    """
    return (abs(a[0] - b[0]) < om2.MVector.kTolerance * max(1.0, max(abs(a[0]), abs(b[0])))
            and abs(a[1] - b[1]) < om2.MVector.kTolerance * max(1.0, max(abs(a[1]), abs(b[1])))
            and abs(a[2] - b[2]) < om2.MVector.kTolerance * max(1.0, max(abs(a[2]), abs(b[2])))
            and abs(a[3] - b[3]) < om2.MVector.kTolerance * max(1.0, max(abs(a[3]), abs(b[3])))
            )


# --------------------------------------------------------------
# --- Vectors / Points ---
# --------------------------------------------------------------

def dotProduct(vector1, vector2):
    """Return the dot product of two vectors, also known as the inner product or scalar product.

    Note:
        This operation is commutative.

    Args:
        vector1 (iterable [numeric]): Vector in 3-dimensional Euclidean space represented by Cartesian coordinates ``[x,y,z]``.
        vector2 (iterable [numeric]): Vector in 3-dimensional Euclidean space represented by Cartesian coordinates ``[x,y,z]``.

    Returns:
        :class:`float`: The dot product of ``vector1`` with ``vector2``.
    """
    return om2.MVector(vector1) * om2.MVector(vector2)


def crossProduct(vector1, vector2):
    """Return the cross product of two vectors.

    Note:
        This operation is non-commutative.
        This operation is anticommutative

    Args:
        vector1 (iterable [numeric]): Vector in 3-dimensional Euclidean space represented by Cartesian coordinates ``[x,y,z]``.
        vector2 (iterable [numeric]): Vector in 3-dimensional Euclidean space represented by Cartesian coordinates ``[x,y,z]``.

    Returns:
        :class:`OpenMaya.MVector`: The cross product of ``vector1`` with ``vector2``.
    """
    return om2.MVector(vector1) ^ om2.MVector(vector2)


def distanceBetween(point1, point2):
    """Return the distance between two points.

    Args:
        point1 (iterable [numeric]): Position in 3-dimensional projective space represented by homogeneous coordinates ``[x,y,z,w]``.
        point2 (iterable [numeric]): Position in 3-dimensional projective space represented by homogeneous coordinates ``[x,y,z,w]``.

    Returns:
        :class:`float`: The distance between ``point1`` and ``point2``.
    """
    return om2.MPoint(point1).distanceTo(om2.MPoint(point2))


def angleBetween(vector1, vector2):
    """Return the unsigned angle between two vectors.

    Args:
        vector1 (iterable [numeric]): Vector in 3-dimensional Euclidean space represented by Cartesian coordinates ``[x,y,z]``.
        vector2 (iterable [numeric]): Vector in 3-dimensional Euclidean space represented by Cartesian coordinates ``[x,y,z]``.

    Returns:
        :class:`float`: The angle between ``point1`` and ``point2`` in radians.
    """
    return om2.MVector(vector1).rotateTo(om2.MVector(vector2)).asAxisAngle()[1]


def axisAngleBetween(vector1, vector2):
    """Return the rotation that will take one vector to another in (axis, angle) form.

    Args:
        vector1 (iterable [numeric]): Vector in 3-dimensional Euclidean space represented by Cartesian coordinates ``[x,y,z]``.
        vector2 (iterable [numeric]): Vector in 3-dimensional Euclidean space represented by Cartesian coordinates ``[x,y,z]``.
    ..

    Returns:
        (:class:`OpenMaya.MVector`, :class:`float`): A two-element :class:`tuple`.

        #. The axis of rotation.
        #. The angle of rotation in radians.
    """
    return om2.MVector(vector1).rotateTo(om2.MVector(vector2)).asAxisAngle()


def eulerBetween(vector1, vector2, rotationOrder=om2.MEulerRotation.kXYZ):
    """Return the rotation that will take one vector to another in euler form.

    Args:
        vector1 (iterable [numeric]): Vector in 3-dimensional Euclidean space represented by Cartesian coordinates ``[x,y,z]``.
        vector2 (iterable [numeric]): Vector in 3-dimensional Euclidean space represented by Cartesian coordinates ``[x,y,z]``.
        rotationOrder (:class:`int`): Type constant from :class:`OpenMaya.MEulerRotation` used to set the rotation order.

    Returns:
        :class:`OpenMaya.MEulerRotation`: The euler rotation that takes ``vector1`` to ``vector2`` with rotation order set to ``rotationOrder``.
    """
    eulerRotation = om2.MVector(vector1).rotateTo(om2.MVector(vector2)).asEulerRotation()
    eulerRotation.reorderIt(rotationOrder)
    return eulerRotation


def quaternionBetween(vector1, vector2):
    """Return the rotation that will take one vector to another in quaternion form.

    Args:
        vector1 (iterable [numeric]): Vector in 3-dimensional Euclidean space represented by Cartesian coordinates ``[x,y,z]``.
        vector2 (iterable [numeric]): Vector in 3-dimensional Euclidean space represented by Cartesian coordinates ``[x,y,z]``.

    Returns:
        :class:`OpenMaya.MQuaternion`: The quaternion rotation that takes ``vector1`` to ``vector2``.
    """
    return om2.MVector(vector1).rotateTo(om2.MVector(vector2))


def averageVector(vector1, vector2, weight=0.5):
    """Return the weighted average of two vectors.

    Args:
        vector1 (iterable [numeric]): Vector in 3-dimensional Euclidean space represented by Cartesian coordinates ``[x,y,z]``.
        vector2 (iterable [numeric]): Vector in 3-dimensional Euclidean space represented by Cartesian coordinates ``[x,y,z]``.
        weight (:class:`float`, optional): Weight the result towards ``vector1`` or ``vector2``. Valid values are in the interval ``[0.0, 1.0]``.
            Small values bias ``vector1``. Large values bias ``vector2``. Defaults to ``0.5`` - no bias.

    Raises:
        :exc:`~exceptions.ValueError`: If ``weight`` is less than ``0.0`` or  greater than ``1.0``.

    Returns:
        :class:`OpenMaya.MVector`: The weighted average of ``vector1`` and ``vector2``.
    """
    if weight < 0.0 or weight > 1.0:
        raise ValueError("Weight not in valid interval: [0, 1]")

    vector1 = om2.MVector(vector1)
    vector2 = om2.MVector(vector2)
    offsetVector = vector2 - vector1
    offsetVector *= weight
    offsetVector += vector1

    return offsetVector


def averagePoint(point1, point2, weight=0.5):
    """Return the weighted average of two positions.

    Args:
        point1 (iterable [numeric]): Position in 3-dimensional projective space represented by homogeneous coordinates ``[x,y,z,w]``.
        point2 (iterable [numeric]): Position in 3-dimensional projective space represented by homogeneous coordinates ``[x,y,z,w]``.
        weight (:class:`float`, optional): Weight the result towards ``point1`` or ``point2``. Valid values are in the interval ``[0.0, 1.0]``.
            Small values bias ``point1``. Large values bias ``point2``. Defaults to ``0.5`` - no bias.

    Raises:
        :exc:`~exceptions.ValueError`: If ``weight`` is less than ``0.0`` or  greater than ``1.0``.

    Returns:
        :class:`OpenMaya.MPoint`: The weighted average of ``point1`` and ``point2``.
    """
    if weight < 0.0 or weight > 1.0:
        raise ValueError("Weight not in valid interval: [0, 1]")

    point1 = om2.MPoint(point1)
    point2 = om2.MPoint(point2)
    displacementVector = point2 - point1
    displacementVector *= weight

    return point1 + displacementVector


def closestPointOnLine(pointOnLine1, pointOnLine2, referencePoint):
    """Given two points that describe a line, find the projected point on that line which is closest to a given reference point.

    Args:
        pointOnLine1 (iterable [numeric]): Position in 3-dimensional projective space represented by homogeneous coordinates ``[x,y,z,w]``.
            Used to define a line in combination with ``pointOnLine2``.
        pointOnLine2 (iterable [numeric]): Position in 3-dimensional projective space represented by homogeneous coordinates ``[x,y,z,w]``.
            Must be different to ``pointOnLine1``.
        referencePoint (iterable [numeric]): Position in 3-dimensional projective space represented by homogeneous coordinates ``[x,y,z,w]``.
            Used as the reference point from which to find closest point on the line defined by ``pointOnLine1`` and ``pointOnLine2``.

    Returns:
        :class:`OpenMaya.MPoint`: The point on the line defined by ``pointOnLine1`` and ``pointOnLine2`` which is closest to the ``referencePoint``.
    """
    startPoint = om2.MPoint(pointOnLine1)
    endPoint = om2.MPoint(pointOnLine2)
    referencePoint = om2.MPoint(referencePoint)

    lineVector = endPoint - startPoint
    referenceOffsetVector = referencePoint - startPoint
    projectedVector = vectorProjection(referenceOffsetVector, lineVector)
    closestPoint = startPoint + projectedVector

    return closestPoint


def vectorProjection(vector1, vector2):
    """Given two vectors, find the projection of the first on the second.

    Args:
        vector1 (iterable [numeric]): Vector in 3-dimensional Euclidean space represented by Cartesian coordinates ``[x,y,z]``.
            Used as the vector to project onto ``vector2``.
        vector2 (iterable [numeric]): Vector in 3-dimensional Euclidean space represented by Cartesian coordinates ``[x,y,z]``.
            Used as the target vector. Must be a non-zero vector.

    Raises:
        :exc:`~exceptions.ValueError`: If ``vector2`` is within the default Maya tolerance of the zero vector ``[0,0,0]``.

    Returns:
        :class:`OpenMaya.MVector`: The vector projection of ``vector1`` on ``vector2``.
    """
    if areCloseVectors(vector2, om2.MVector.kZeroVector):
        raise ValueError("Target vector cannot be [0,0,0]")

    vector1 = om2.MVector(vector1)
    vector2 = om2.MVector(vector2)

    dot = vector1 * vector2
    projectedMagnitude = dot / vector2.length()
    projectedVector = projectedMagnitude * vector2.normal()

    return projectedVector


def centerPoint(points):
    """Return the centroid of a set of points.

    Args:
        points (iterable [iterable [numeric]]): Array of positions in 3-dimensional projective space each represented by homogeneous coordinates ``[x,y,z,w]``.

    Raises:
        :exc:`~exceptions.ValueError`: If ``points`` is empty.

    Returns:
        :class:`OpenMaya.MPoint`: The centroid for the set of ``points``.
    """
    if len(points) == 0:
        raise ValueError("Centroid undefined for empty set")

    combinedVector = om2.MVector(om2.MVector.kZeroVector)

    for point in points:
        # Get the cartesianized displacement of each point from the origin
        combinedVector += point - om2.MPoint.kOrigin

    centroid = om2.MPoint.kOrigin + (combinedVector / len(points))

    return centroid


def mirrorPoint(point, axis=om2.MVector.kXaxis):
    """Return a point mirrored through a plane represented by an axis.

    Args:
        point (iterable [numeric]): Position in 3-dimensional projective space represented by homogeneous coordinates ``[x,y,z,w]``.
        axis (:class:`int`, optional): Type constant from :class:`OpenMaya.MVector` representing the plane to mirror ``point`` through. Valid values are:

            - :attr:`OpenMaya.MVector.kXaxis`: Mirror in the YZ plane.
            - :attr:`OpenMaya.MVector.kYaxis`: Mirror in the XZ plane.
            - :attr:`OpenMaya.MVector.kZaxis`: Mirror in the XY plane.

            Defaults to :attr:`OpenMaya.MVector.kXaxis`.

    Returns:
        :class:`OpenMaya.MPoint`: Mirrored point.
    """
    point = om2.MPoint(point)
    point[axis] *= -1

    return point


# --------------------------------------------------------------
# --- Matrices ---
# --------------------------------------------------------------

def mirrorMatrix(matrix, axis=om2.MVector.kXaxis, rotation=True, translation=True):
    """Return a transformation matrix composed of transforms which have been mirrored through a plane.

    Args:
        matrix (:class:`OpenMaya.MMatrix` | :class:`OpenMaya.MFloatMatrix`): Transformation matrix.
        axis (:class:`int`, optional): Type constant from :class:`OpenMaya.MVector` representing the plane to mirror transforms of ``matrix`` through. Valid values are:

            - :attr:`OpenMaya.MVector.kXaxis`: Mirror in the YZ plane.
            - :attr:`OpenMaya.MVector.kYaxis`: Mirror in the XZ plane.
            - :attr:`OpenMaya.MVector.kZaxis`: Mirror in the XY plane.

            Defaults to :attr:`OpenMaya.MVector.kXaxis`.
        rotation (:class:`bool`, optional): Whether to mirror the rotation transforms of ``matrix``. Defaults to :data:`True`.
        translation (:class:`bool`, optional): Whether to mirror the translation transforms of ``matrix``. Defaults to :data:`True`.

    Returns:
        :class:`OpenMaya.MMatrix`: Transformation matrix corresponding to ``matrix``, mirrored according to the ``translation`` and ``rotation`` arguments.
    """
    # Transforms are applied relative to the mirroring rotations meaning it is unncessary to decompose the input
    mirroredMatrix = om2.MMatrix(matrix)

    planeAxes = [0, 1, 2]
    planeAxes.remove(axis)

    if rotation:
        # For each basis vector, negate the coordinates corresponding to the axes of the mirroring plane
        for planeAxis in planeAxes:
            mirroredMatrix[0 + planeAxis] *= -1
            mirroredMatrix[4 + planeAxis] *= -1
            mirroredMatrix[8 + planeAxis] *= -1

    if translation:
        # Negate the coordinate corresponding to the mirror axis
        mirroredMatrix[12 + axis] *= -1

    return mirroredMatrix


def extractScaleMatrix(matrix):
    """Extract a matrix representing just the scale transforms of a transformation matrix.

    Note:
        See :ref:`note-4 <note_4>` regarding assumptions pertinent to the extraction.

    Args:
        matrix (:class:`OpenMaya.MMatrix` | :class:`OpenMaya.MFloatMatrix`): Transformation matrix.

    Returns:
        :class:`OpenMaya.MMatrix`: Scale matrix extracted from ``matrix``.
    """
    scaleX = (matrix.getElement(0, 0) * matrix.getElement(0, 0) + matrix.getElement(0, 1) * matrix.getElement(0, 1) + matrix.getElement(0, 2) * matrix.getElement(0, 2)) ** 0.5
    scaleY = (matrix.getElement(1, 0) * matrix.getElement(1, 0) + matrix.getElement(1, 1) * matrix.getElement(1, 1) + matrix.getElement(1, 2) * matrix.getElement(1, 2)) ** 0.5
    scaleZ = (matrix.getElement(2, 0) * matrix.getElement(2, 0) + matrix.getElement(2, 1) * matrix.getElement(2, 1) + matrix.getElement(2, 2) * matrix.getElement(2, 2)) ** 0.5

    # The determinant tests the handedness of our basis: (x ^ y) * z < 0
    # If it is negative, there is an odd number of reflections (ie. one axis has a negative scale)
    # If it is positive, there are either no reflections or 2 reflections(ie. 2 axes may have a negative scale)
    # However two reflections is the same as a 180 degree rotation around the third axis (it is impossible to extract the correct information)
    # Therefore we only handle the single reflection case by negating the z - axis (this is how the API handles it)
    if matrix.det3x3() < 0.0:
        scaleZ *= -1

    scaleMatrix = om2.MMatrix(om2.MMatrix.kIdentity)
    scaleMatrix.setElement(0, 0, scaleX)
    scaleMatrix.setElement(1, 1, scaleY)
    scaleMatrix.setElement(2, 2, scaleZ)

    return scaleMatrix


def extractScale(matrix):
    """Extract the scale transforms from a transformation matrix.

    Note:
        See :ref:`note-4 <note_4>` regarding assumptions pertinent to the extraction.

    Args:
        matrix (:class:`OpenMaya.MMatrix` | :class:`OpenMaya.MFloatMatrix`): Transformation matrix.

    Returns:
        :class:`OpenMaya.MVector`: Scale extracted from ``matrix``, for which elements correspond to the 3-dimensional Cartesian axes ``[x,y,z]``.
    """
    scaleX = (matrix.getElement(0, 0) * matrix.getElement(0, 0) + matrix.getElement(0, 1) * matrix.getElement(0, 1) + matrix.getElement(0, 2) * matrix.getElement(0, 2)) ** 0.5
    scaleY = (matrix.getElement(1, 0) * matrix.getElement(1, 0) + matrix.getElement(1, 1) * matrix.getElement(1, 1) + matrix.getElement(1, 2) * matrix.getElement(1, 2)) ** 0.5
    scaleZ = (matrix.getElement(2, 0) * matrix.getElement(2, 0) + matrix.getElement(2, 1) * matrix.getElement(2, 1) + matrix.getElement(2, 2) * matrix.getElement(2, 2)) ** 0.5

    if matrix.det3x3() < 0.0:
        scaleZ *= -1

    return om2.MVector(scaleX, scaleY, scaleZ)


def extractRotationMatrix(matrix):
    """Extract a matrix representing just the rotation transforms of a transformation matrix.

    This will include any encoded rotation, jointOrient, rotationOrientation.

    Note:
        See :ref:`note-4 <note_4>` regarding assumptions pertinent to the extraction.

    Args:
        matrix (:class:`OpenMaya.MMatrix` | :class:`OpenMaya.MFloatMatrix`): Transformation matrix.

    Returns:
        :class:`OpenMaya.MMatrix`: Rotation matrix extracted from ``matrix``.
    """
    rotationMatrix = om2.MMatrix(om2.MMatrix.kIdentity)
    scale = extractScale(matrix)

    if not areClose(scale.x, 0.0):
        mult = 1.0 / scale.x
        rotationMatrix.setElement(0, 0, matrix.getElement(0, 0) * mult)
        rotationMatrix.setElement(0, 1, matrix.getElement(0, 1) * mult)
        rotationMatrix.setElement(0, 2, matrix.getElement(0, 2) * mult)
    else:
        rotationMatrix.setElement(0, 0, 0.0)

    if not areClose(scale.y, 0.0):
        mult = 1.0 / scale.y
        rotationMatrix.setElement(1, 0, matrix.getElement(1, 0) * mult)
        rotationMatrix.setElement(1, 1, matrix.getElement(1, 1) * mult)
        rotationMatrix.setElement(1, 2, matrix.getElement(1, 2) * mult)
    else:
        rotationMatrix.setElement(1, 1, 0.0)

    if not areClose(scale.z, 0.0):
        mult = 1.0 / scale.z
        rotationMatrix.setElement(2, 0, matrix.getElement(2, 0) * mult)
        rotationMatrix.setElement(2, 1, matrix.getElement(2, 1) * mult)
        rotationMatrix.setElement(2, 2, matrix.getElement(2, 2) * mult)
    else:
        rotationMatrix.setElement(2, 2, 0.0)

    return rotationMatrix


def extractEulerRotation(matrix, rotationOrder=om2.MEulerRotation.kXYZ):
    """Extract the rotation transforms from a transformation matrix in euler form.

    This will include any encoded rotation, jointOrient, rotationOrientation.

    Note:
        See :ref:`note-4 <note_4>` regarding assumptions pertinent to the extraction.

    Args:
        matrix (:class:`OpenMaya.MMatrix` | :class:`OpenMaya.MFloatMatrix`): Transformation matrix.
        rotationOrder (:class:`int`): Type constant from :class:`OpenMaya.MEulerRotation` used to extract the rotation from ``matrix``.
            This should be the same order that was used to encode the rotations.

    Returns:
        :class:`OpenMaya.MEulerRotation`: Euler rotation extracted from ``matrix``.
    """
    # NOTE: Maya's API provides two ways we can extract rotation
    # - The MEulerRotation.decompose() method does not account for non-uniform scaling, we must provide it a normalized rotation matrix
    # - The MTransformationMatrix.rotation() method accounts for non-uniform scaling, we must then call MEulerRotation.reorderIt() on the result
    rotationMatrix = extractRotationMatrix(matrix)
    return om2.MEulerRotation.decompose(rotationMatrix, rotationOrder)


def extractQuaternionRotation(matrix):
    """Extract the rotation transforms from a transformation matrix in quaternion form.

    This will include any encoded rotation, jointOrient, rotationOrientation.

    Note:
        See :ref:`note-4 <note_4>` regarding assumptions pertinent to the extraction.

    Args:
        matrix (:class:`OpenMaya.MMatrix` | :class:`OpenMaya.MFloatMatrix`): Transformation matrix.

    Returns:
        :class:`OpenMaya.MQuaternion`: Quaternion rotation extracted from ``matrix``.
    """
    # Rotation conversion: https://www.euclideanspace.com/maths/geometry/rotations/conversions/matrixToQuaternion/
    rotation = om2.MQuaternion(om2.MQuaternion.kIdentity)
    rotationMatrix = extractRotationMatrix(matrix)

    rotation.w = (max(0.0, 1.0 + rotationMatrix.getElement(0, 0) + rotationMatrix.getElement(1, 1) + rotationMatrix.getElement(2, 2))) ** 0.5 * 0.5
    rotation.x = (max(0.0, 1.0 + rotationMatrix.getElement(0, 0) - rotationMatrix.getElement(1, 1) - rotationMatrix.getElement(2, 2))) ** 0.5 * 0.5
    rotation.y = (max(0.0, 1.0 - rotationMatrix.getElement(0, 0) + rotationMatrix.getElement(1, 1) - rotationMatrix.getElement(2, 2))) ** 0.5 * 0.5
    rotation.z = (max(0.0, 1.0 - rotationMatrix.getElement(0, 0) - rotationMatrix.getElement(1, 1) + rotationMatrix.getElement(2, 2))) ** 0.5 * 0.5
    rotation.x = math.copysign(rotation.x, -1 * (rotationMatrix.getElement(2, 1) - rotationMatrix.getElement(1, 2)))
    rotation.y = math.copysign(rotation.y, -1 * (rotationMatrix.getElement(0, 2) - rotationMatrix.getElement(2, 0)))
    rotation.z = math.copysign(rotation.z, -1 * (rotationMatrix.getElement(1, 0) - rotationMatrix.getElement(0, 1)))

    return rotation


def extractTranslationMatrix(matrix, space=om2.MSpace.kTransform):
    """Extract a matrix representing just the translation transforms of a transformation matrix.

    Args:
        matrix (:class:`OpenMaya.MMatrix` | :class:`OpenMaya.MFloatMatrix`): Transformation matrix.
        space (:class:`int`): Type constant from :class:`OpenMaya.MSpace` representing the space in which to extract the translation.
            Valid values are:

            - :attr:`OpenMaya.MSpace.kTransform`, :attr:`OpenMaya.MSpace.kPostTransform`: Depicts a space in which translation is unaffected by other transforms.
              Useful when ``matrix`` represents a standard encoding of [scale] x [rotation] x [translation].
            - :attr:`OpenMaya.MSpace.kPreTransform`: Depicts a space in which translation is affected by other transforms.
              Useful when ``matrix`` represents a non-standard encoding of [translation] x [scale] x [rotation].

    Raises:
        :exc:`~exceptions.ValueError`: If ``space`` is not one of the accepted type constants.

    Returns:
        :class:`OpenMaya.MMatrix`: Translation matrix extracted from ``matrix``.
    """
    if space == om2.MSpace.kTransform or space == om2.MSpace.kPostTransform:
        return om2.MMatrix([(1, 0, 0, 0), (0, 1, 0, 0), (0, 0, 1, 0), (matrix[12], matrix[13], matrix[14], matrix[15])])
    elif space == om2.MSpace.kPreTransform:
        # This space depicts translation as being affected by the other transforms (not generally the case)
        # We want the effects of the rotation and scale to "revert" the translation to a "pre-transformed" state
        # Pre-multiplying the inverse matrices by the matrix itself ensures the inverted effort is applied to the translation
        # If M = T * S * R (translation applied last), then T = M * R^-1 * S^-1
        rotationMatrix = extractRotationMatrix(matrix)
        scaleMatrix = extractScaleMatrix(matrix)
        return matrix * rotationMatrix.inverse() * scaleMatrix.inverse()
    else:
        raise ValueError("`space` expects one of: OpenMaya.MSpace.kTransform, OpenMaya.MSpace.kPostTransform, OpenMaya.MSpace.kPreTransform")


def extractTranslation(matrix, space=om2.MSpace.kTransform):
    """Extract the translation transforms from a transformation matrix.

    Args:
        matrix (:class:`OpenMaya.MMatrix` | :class:`OpenMaya.MFloatMatrix`): Transformation matrix.
        space (:class:`int`): Type constant from :class:`OpenMaya.MSpace` representing the space in which to extract the translation.
            Valid values are:

            - :attr:`OpenMaya.MSpace.kTransform`, :attr:`OpenMaya.MSpace.kPostTransform`: Depicts a space in which translation is unaffected by other transforms.
              Useful when ``matrix`` represents a standard encoding of [scale] x [rotation] x [translation].
            - :attr:`OpenMaya.MSpace.kPreTransform`: Depicts a space in which translation is affected by other transforms.
              Useful when ``matrix`` represents a non-standard encoding of [translation] x [scale] x [rotation].

    Raises:
        :exc:`~exceptions.ValueError`: If ``space`` is not one of the accepted type constants.

    Returns:
        :class:`OpenMaya.MVector`: Translation extracted from ``matrix``.
    """
    if space == om2.MSpace.kTransform or space == om2.MSpace.kPostTransform:
        return om2.MVector(matrix[12], matrix[13], matrix[14])
    elif space == om2.MSpace.kPreTransform:
        preTranslationMatrix = extractTranslationMatrix(matrix, space=om2.MSpace.kPreTransform)
        return om2.MVector(preTranslationMatrix[12], preTranslationMatrix[13], preTranslationMatrix[14])
    else:
        raise ValueError("`space` expects one of: OpenMaya.MSpace.kTransform, OpenMaya.MSpace.kPostTransform, OpenMaya.MSpace.kPreTransform")


def splitMatrix(matrix):
    """Extract matrices representing the individual transforms of a transformation matrix.

    Note:
        Transforms will be extracted in :attr:`OpenMaya.MSpace.kTransform` space,
        therefore ``matrix`` should represent a standard encoding of [scale] x [rotation] x [translation].

    Args:
        matrix (:class:`OpenMaya.MMatrix` | :class:`OpenMaya.MFloatMatrix`): Transformation matrix.

    Returns:
        (:class:`OpenMaya.MMatrix`, :class:`OpenMaya.MMatrix`, :class:`OpenMaya.MMatrix`): A three-element :class:`tuple`.

        #. Translation matrix extracted from ``matrix``.
        #. Rotation matrix extracted from ``matrix``.
        #. Scale matrix extracted from ``matrix``.
    """
    # If all transforms are required, completing the extractions as a single operation is more efficient
    scaleMatrix, rotationMatrix, translationMatrix = om2.MMatrix(om2.MMatrix.kIdentity)
    scale = extractScale(matrix)

    scaleMatrix.setElement(0, 0, scale.x)
    scaleMatrix.setElement(1, 1, scale.y)
    scaleMatrix.setElement(2, 2, scale.z)

    if not areClose(scale.x, 0.0):
        mult = 1.0 / scale.x
        rotationMatrix.setElement(0, 0, matrix.getElement(0, 0) * mult)
        rotationMatrix.setElement(0, 1, matrix.getElement(0, 1) * mult)
        rotationMatrix.setElement(0, 2, matrix.getElement(0, 2) * mult)
    else:
        rotationMatrix.setElement(0, 0, 0.0)

    if not areClose(scale.y, 0.0):
        mult = 1.0 / scale.y
        rotationMatrix.setElement(1, 0, matrix.getElement(1, 0) * mult)
        rotationMatrix.setElement(1, 1, matrix.getElement(1, 1) * mult)
        rotationMatrix.setElement(1, 2, matrix.getElement(1, 2) * mult)
    else:
        rotationMatrix.setElement(1, 1, 0.0)

    if not areClose(scale.z, 0.0):
        mult = 1.0 / scale.z
        rotationMatrix.setElement(2, 0, matrix.getElement(2, 0) * mult)
        rotationMatrix.setElement(2, 1, matrix.getElement(2, 1) * mult)
        rotationMatrix.setElement(2, 2, matrix.getElement(2, 2) * mult)
    else:
        rotationMatrix.setElement(2, 2, 0.0)

    translationMatrix.setElement(3, 0, matrix.getElement(3, 0))
    translationMatrix.setElement(3, 1, matrix.getElement(3, 1))
    translationMatrix.setElement(3, 2, matrix.getElement(3, 2))
    translationMatrix.setElement(3, 3, matrix.getElement(3, 3))

    return translationMatrix, rotationMatrix, scaleMatrix


def composeMatrix(translation, rotation, scale):
    """Compose a transformation matrix from the given transforms.

    Args:
        translation (iterable [numeric]): Translation in 3-dimensional Euclidean space represented by Cartesian coordinates ``[x,y,z]``.
        rotation (:class:`OpenMaya.MEulerRotation` | :class:`OpenMaya.MQuaternion`): Rotation in 3-dimensional Euclidean space.
        scale (iterable [numeric]): Scaling in 3-dimensional Euclidean space for which elements correspond to the Cartesian axes ``[x,y,z]``.

    Returns:
        :class:`OpenMaya.MMatrix`: Transformation matrix composed of [``scale``] x [``rotation``] x [``translation``].
    """
    transMatrix = om2.MTransformationMatrix()
    transMatrix.setTranslation(translation, om2.MSpace.kTransform)
    transMatrix.setRotation(rotation)
    transMatrix.setScale(scale, om2.MSpace.kTransform)
    return transMatrix.asMatrix()


def decomposeMatrix(matrix, rotationOrder=om2.MEulerRotation.kXYZ, rotationAsQuarternion=False):
    """Decompose a transformation matrix into its constituent transforms.

    Note:
        Transforms will be extracted in :attr:`OpenMaya.MSpace.kTransform` space,
        therefore ``matrix`` should represent a standard encoding of [scale] x [rotation] x [translation].

    Args:
        matrix (:class:`OpenMaya.MMatrix` | :class:`OpenMaya.MFloatMatrix`): Transformation matrix.
        rotationOrder (:class:`int`): Type constant from :class:`OpenMaya.MEulerRotation`.
            Used to extract the rotation from ``matrix`` if ``rotationAsQuarternion`` is :data:`False`.
            Defaults to :attr:`OpenMaya.MEulerRotation.kXYZ`.
        rotationAsQuarternion (:class:`bool`): Whether to extract rotation transforms as a quaternion instead of an euler rotation.
            Defaults to :data:`False`.
    ..

    Returns:
        (:class:`OpenMaya.MVector`, :class:`OpenMaya.MEulerRotation` | :class:`OpenMaya.MQuaternion`, :class:`OpenMaya.MVector`): A three-element :class:`tuple`.

        #. Translation extracted from ``matrix``.
        #. Rotation extracted from ``matrix`` in quaternion form if ``rotationAsQuarternion`` is :data:`True`, otherwise in euler form.
        #. Scale extracted from ``matrix``.
    """
    translation = extractTranslation(matrix)
    scale = extractScale(matrix)
    rotationMatrix = om2.MMatrix(om2.MMatrix.kIdentity)

    if not areClose(scale.x, 0.0):
        mult = 1.0 / scale.x
        rotationMatrix.setElement(0, 0, matrix.getElement(0, 0) * mult)
        rotationMatrix.setElement(0, 1, matrix.getElement(0, 1) * mult)
        rotationMatrix.setElement(0, 2, matrix.getElement(0, 2) * mult)
    else:
        rotationMatrix.setElement(0, 0, 0.0)

    if not areClose(scale.y, 0.0):
        mult = 1.0 / scale.y
        rotationMatrix.setElement(1, 0, matrix.getElement(1, 0) * mult)
        rotationMatrix.setElement(1, 1, matrix.getElement(1, 1) * mult)
        rotationMatrix.setElement(1, 2, matrix.getElement(1, 2) * mult)
    else:
        rotationMatrix.setElement(1, 1, 0.0)

    if not areClose(scale.z, 0.0):
        mult = 1.0 / scale.z
        rotationMatrix.setElement(2, 0, matrix.getElement(2, 0) * mult)
        rotationMatrix.setElement(2, 1, matrix.getElement(2, 1) * mult)
        rotationMatrix.setElement(2, 2, matrix.getElement(2, 2) * mult)
    else:
        rotationMatrix.setElement(2, 2, 0.0)

    if rotationAsQuarternion:
        rotation = om2.MQuaternion(om2.MQuaternion.kIdentity)
        rotation.w = (max(0.0, 1.0 + rotationMatrix.getElement(0, 0) + rotationMatrix.getElement(1, 1) + rotationMatrix.getElement(2, 2))) ** 0.5 * 0.5
        rotation.x = (max(0.0, 1.0 + rotationMatrix.getElement(0, 0) - rotationMatrix.getElement(1, 1) - rotationMatrix.getElement(2, 2))) ** 0.5 * 0.5
        rotation.y = (max(0.0, 1.0 - rotationMatrix.getElement(0, 0) + rotationMatrix.getElement(1, 1) - rotationMatrix.getElement(2, 2))) ** 0.5 * 0.5
        rotation.z = (max(0.0, 1.0 - rotationMatrix.getElement(0, 0) - rotationMatrix.getElement(1, 1) + rotationMatrix.getElement(2, 2))) ** 0.5 * 0.5
        rotation.x = math.copysign(rotation.x, -1 * (rotationMatrix.getElement(2, 1) - rotationMatrix.getElement(1, 2)))
        rotation.y = math.copysign(rotation.y, -1 * (rotationMatrix.getElement(0, 2) - rotationMatrix.getElement(2, 0)))
        rotation.z = math.copysign(rotation.z, -1 * (rotationMatrix.getElement(1, 0) - rotationMatrix.getElement(0, 1)))
    else:
        rotationMatrix = extractRotationMatrix(matrix)
        rotation = om2.MEulerRotation.decompose(rotationMatrix, rotationOrder)

    return translation, rotation, scale


# The following operations are given as alternative implementations when a matrix contains shearing transforms:
"""
def extractScaleMatrix(matrix):
    transMatrix = om2.MTransformationMatrix(matrix)
    scaleShearMatrix = transMatrix.asScaleMatrix()
    shear = transMatrix.shear(om2.MSpace.kTransform)
    shearMatrix = om2.MMatrix([(1, 0, 0, 0), (shear[0], 1, 0, 0), (shear[1], shear[2], 1, 0), (0, 0, 0, 1)])
    scaleMatrix = scaleShearMatrix * shearMatrix.inverse()
    return scaleMatrix

def extractScale(matrix):
    transMatrix = om2.MTransformationMatrix(matrix)
    return om2.MVector(transMatrix.scale(om2.MSpace.kTransform))

def extractRotationMatrix(matrix):
    transMatrix = om2.MTransformationMatrix(matrix)
    scaleShearRotationMatrix = transMatrix.asRotateMatrix()
    scaleShearMatrix = transMatrix.asScaleMatrix()
    # Remove the scale and shear transforms from the rotation matrix (ie. (S * Sh)^-1 * (S * Sh) * R)
    return scaleShearMatrix.inverse() * scaleShearRotationMatrix

def extractTranslationMatrix(matrix, space=om2.MSpace.kTransform):
    if space == om2.MSpace.kTransform or space == om2.MSpace.kPostTransform:
        return om2.MMatrix([(1, 0, 0, 0), (0, 1, 0, 0), (0, 0, 1, 0), (matrix[12], matrix[13], matrix[14], matrix[15])])
    elif space == om2.MSpace.kPreTransform:
        transMatrix = om2.MTransformationMatrix(matrix)
        preTranslation = transMatrix.translation(om2.MSpace.kPreTransform)
        return om2.MMatrix([(1, 0, 0, 0), (0, 1, 0, 0), (0, 0, 1, 0), (preTranslation[0], preTranslation[1], preTranslation[2], 1)])
    else:
        raise ValueError("`space` argument expected one of: OpenMaya.MSpace.kTransform, OpenMaya.MSpace.kPostTransform, OpenMaya.MSpace.kPreTransform")

def splitMatrix(matrix):
    transMatrix = om2.MTransformationMatrix(matrix)

    # SHEAR
    shear = transMatrix.shear(om2.MSpace.kTransform)
    shearMatrix = om2.MMatrix([(1, 0, 0, 0), (shear[0], 1, 0, 0), (shear[1], shear[2], 1, 0), (0, 0, 0, 1)])

    # SCALE
    scaleShearMatrix = transMatrix.asScaleMatrix()
    scaleMatrix = scaleShearMatrix * shearMatrix.inverse()

    # ROTATION
    scaleShearRotationMatrix = transMatrix.asRotateMatrix()
    rotationMatrix = scaleShearMatrix.inverse() * scaleShearRotationMatrix

    # TRANSLATION
    translationMatrix = om2.MMatrix([(1, 0, 0, 0), (0, 1, 0, 0), (0, 0, 1, 0), (matrix[12], matrix[13], matrix[14], matrix[15])])

    return translationMatrix, rotationMatrix, shearMatrix, scaleMatrix

def composeMatrix(translation, rotation, scale, shear):
    transMatrix = om2.MTransformationMatrix()
    transMatrix.setTranslation(translation, om2.MSpace.kTransform)
    transMatrix.setRotation(rotation)
    transMatrix.setShear(shear, om2.MSpace.kTransform)
    transMatrix.setScale(scale, om2.MSpace.kTransform)
    return transMatrix.asMatrix()

def decomposeMatrix(matrix, rotationOrder=om2.MEulerRotation.kXYZ, rotationAsQuaternion=False):
    transMatrix = om2.MTransformationMatrix(matrix)

    translation = transMatrix.translation(om2.MSpace.kTransform)
    rotation = transMatrix.rotation(asQuaternion=rotationAsQuaternion)
    scale = transMatrix.scale(om2.MSpace.kTransform)
    shear = transMatrix.shear(om2.MSpace.kTransform)

    if not rotationAsQuaternion:
        # Rotation will always be extracted in XYZ order, we must reorder it if necessary
        if rotationOrder != om2.MEulerRotation.kXYZ:
            rotation.reorderIt(rotationOrder)

    return translation, rotation, scale, shear
"""
