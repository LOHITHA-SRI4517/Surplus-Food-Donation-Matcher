
def find_best_match(db, category, city, quantity):
    """
    Find NGOs that support the food category, operate in the
    same city, and have enough available capacity.

    Returns a sorted list of matching NGOs.
    """

    ngos = db.execute(
        """
        SELECT id, code, name, city, categories, capacity
        FROM ngos
        WHERE available = 1
          AND capacity >= ?
          AND lower(trim(city)) = lower(trim(?))
        """,
        (quantity, city)
    ).fetchall()

    candidates = []

    requested_category = category.strip().lower()

    for ngo in ngos:
        supported_categories = [
            item.strip().lower()
            for item in ngo["categories"].split(",")
        ]

        if requested_category not in supported_categories:
            continue

        # Transparent demo score: each eligible NGO gets 100 points.
        candidates.append({
            "id": ngo["id"],
            "name": ngo["name"],
            "code": ngo["code"],
            "score": 100,
            "capacity": ngo["capacity"]
        })

    # Sort by score descending, then NGO name alphabetically.
    candidates.sort(
        key=lambda item: (-item["score"], item["name"].lower())
    )

    return candidates
