from app.services.rating import calculate_rating_average


def test_calculate_rating_average_for_first_review():
    assert calculate_rating_average(0.0, 0, 5) == (5.0, 1)


def test_calculate_rating_average_rounds_to_two_digits():
    assert calculate_rating_average(4.0, 2, 5) == (4.33, 3)
