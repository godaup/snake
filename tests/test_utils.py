import pytest

from snake_quest.utils import Vec2


def test_add_and_sub():
    assert Vec2(1, 2) + Vec2(3, 4) == Vec2(4, 6)
    assert Vec2(1, 2) - Vec2(3, 5) == Vec2(-2, -3)


def test_scalar_mul():
    assert Vec2(1, -2) * 3 == Vec2(3, -6)
    assert Vec2(2, 4) * 0.5 == Vec2(1, 2)


def test_length():
    assert Vec2(3, 4).length() == pytest.approx(5)
    assert Vec2().length() == 0


@pytest.mark.parametrize("other", [1, "a", None])
def test_add_rejects_non_vectors(other):
    with pytest.raises(TypeError):
        Vec2(1, 1) + other


@pytest.mark.parametrize("other", [Vec2(1, 1), "a", None])
def test_mul_rejects_non_scalars(other):
    with pytest.raises(TypeError):
        Vec2(1, 1) * other
